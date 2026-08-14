#!/usr/bin/env python3
"""Observe a MIPS guest write through QEMU's localhost GDB remote protocol."""

from __future__ import annotations

import argparse
import json
import socket
import time


def checksum(payload: bytes) -> bytes:
    return f"{sum(payload) & 0xff:02x}".encode("ascii")


class GdbRemote:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.socket = socket.create_connection((host, port), timeout=timeout)
        self.socket.settimeout(timeout)

    def close(self) -> None:
        self.socket.close()

    def _read_byte(self) -> bytes:
        value = self.socket.recv(1)
        if not value:
            raise EOFError("QEMU closed the GDB connection")
        return value

    def receive(self) -> str:
        while True:
            byte = self._read_byte()
            if byte in (b"+", b"-"):
                continue
            if byte != b"$":
                continue
            payload = bytearray()
            while True:
                byte = self._read_byte()
                if byte == b"#":
                    break
                if byte == b"}":
                    payload.append(self._read_byte()[0] ^ 0x20)
                else:
                    payload.extend(byte)
            received_checksum = self.socket.recv(2)
            valid = received_checksum.lower() == checksum(payload)
            self.socket.sendall(b"+" if valid else b"-")
            if valid:
                return payload.decode("ascii", errors="replace")

    def command(self, command: str) -> str:
        payload = command.encode("ascii")
        self.socket.sendall(b"$" + payload + b"#" + checksum(payload))
        response = self.receive()
        while response.startswith("O") and len(response) % 2 == 1:
            response = self.receive()
        return response


def read_u32(remote: GdbRemote, address: int) -> int:
    response = remote.command(f"m{address:x},4")
    if response.startswith("E") or len(response) != 8:
        raise RuntimeError(f"cannot read 0x{address:08x}: {response}")
    return int.from_bytes(bytes.fromhex(response), "little")


def read_register(remote: GdbRemote, register: int) -> int | None:
    response = remote.command(f"p{register:x}")
    if response.startswith("E") or response.startswith("x") or len(response) != 8:
        return None
    return int.from_bytes(bytes.fromhex(response), "little")


def write_register(remote: GdbRemote, register: int, value: int) -> None:
    encoded = value.to_bytes(4, "little").hex()
    response = remote.command(f"P{register:x}={encoded}")
    if response != "OK":
        raise RuntimeError(
            f"cannot write register {register} with 0x{value:08x}: {response}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--address", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected", type=lambda value: int(value, 0))
    parser.add_argument("--length", type=int, default=4)
    parser.add_argument("--max-stops", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    remote = GdbRemote(args.host, args.port, args.timeout)
    events: list[dict[str, int | str | None]] = []
    started = time.monotonic()
    try:
        supported = remote.command("qSupported:multiprocess+;swbreak+;hwbreak+")
        watch_result = remote.command(
            f"Z2,{args.address:x},{args.length:x}"
        )
        if watch_result != "OK":
            raise RuntimeError(f"QEMU rejected write watchpoint: {watch_result}")

        stop_reason = remote.command("c")
        for index in range(args.max_stops):
            value = read_u32(remote, args.address)
            event = {
                "index": index,
                "reason": stop_reason,
                "address": args.address,
                "value": value,
                "pc": read_register(remote, 37),
                "sp": read_register(remote, 29),
                "ra": read_register(remote, 31),
            }
            events.append(event)
            print(json.dumps(event, sort_keys=True), flush=True)
            if args.expected is None or value == args.expected:
                break
            remove_result = remote.command(
                f"z2,{args.address:x},{args.length:x}"
            )
            if remove_result != "OK":
                raise RuntimeError(
                    f"QEMU could not remove write watchpoint: {remove_result}"
                )
            pc = event["pc"]
            if not isinstance(pc, int):
                raise RuntimeError("QEMU did not expose the MIPS PC register")
            # QEMU reports a committed MIPS store with PC still on the store.
            # Advancing PC avoids retriggering the same completed instruction.
            write_register(remote, 37, pc + 4)
            watch_result = remote.command(
                f"Z2,{args.address:x},{args.length:x}"
            )
            if watch_result != "OK":
                raise RuntimeError(
                    f"QEMU could not restore write watchpoint: {watch_result}"
                )
            stop_reason = remote.command("c")
        else:
            raise RuntimeError(
                f"expected write was not observed in {args.max_stops} stops"
            )
    finally:
        remote.close()

    print(
        json.dumps(
            {
                "format": "h1-qemu-mips-watch-v1",
                "supported": supported,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "events": events,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
