import { EventEmitter } from "node:events";
import { io, type Socket } from "socket.io-client";

import { applyDeltas, type Delta, type State } from "./state.ts";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export type Address = { host: string; port: number };

export const DEFAULT_ADDRESS: Address = { host: "localhost", port: 5500 };

/** A command's answer, or why HyperDrive couldn't be reached. */
export type CommandResult = { ok: boolean; status: number; body: string };

type Events = {
	/** The state changed (coalesced: at most once per tick) */
	state: [];
	status: [ConnectionStatus];
};

/**
 * Normalizes what a user typed as HyperDrive's address: "192.168.1.5",
 * "http://pc.local:5500/" or "pc:5501" (a port typed with the host wins).
 */
export function parseAddress(host: unknown, port: unknown): Address {
	let h = typeof host === "string" ? host.trim() : "";
	let p = Number(port);
	h = h.replace(/^[a-z]+:\/\//i, "").replace(/\/.*$/, "");
	const withPort = /^(.*):(\d+)$/.exec(h);
	if (withPort && !withPort[1].includes(":")) {
		h = withPort[1];
		p = Number(withPort[2]);
	}
	return {
		host: h || DEFAULT_ADDRESS.host,
		port: Number.isInteger(p) && p > 0 && p < 65536 ? p : DEFAULT_ADDRESS.port,
	};
}

export function baseUrl(address: Address): string {
	// IPv6 addresses need brackets in URLs
	const host = address.host.includes(":") && !address.host.startsWith("[") ? `[${address.host}]` : address.host;
	return `http://${host}:${address.port}`;
}

/**
 * The plugin's one connection to HyperDrive: socket.io for the state, and
 * the web server's links for commands (their answers tell a failed command
 * apart, so the key can show an alert).
 */
export class HyperDriveConnection extends EventEmitter<Events> {
	state: State = {};
	status: ConnectionStatus = "disconnected";
	address: Address = DEFAULT_ADDRESS;

	#socket: Socket | undefined;
	#deltaIndex: number | undefined;
	#stateQueued = false;
	readonly #timeoutMs: number;

	constructor(options: { timeoutMs?: number } = {}) {
		super();
		this.#timeoutMs = options.timeoutMs ?? 5000;
	}

	get url(): string {
		return baseUrl(this.address);
	}

	/** Connects to HyperDrive, or reconnects if the address changed. */
	connect(address: Address = this.address): void {
		if (this.#socket && address.host === this.address.host && address.port === this.address.port) {
			return;
		}
		this.disconnect();
		this.address = address;
		this.#setStatus("connecting");

		const socket = io(this.url, {
			transports: ["websocket"],
			reconnection: true,
			reconnectionDelay: 1000,
			reconnectionDelayMax: 5000,
			timeout: 5000,
		});
		this.#socket = socket;

		socket.on("connect", () => this.#setStatus("connected"));
		socket.on("disconnect", () => this.#setStatus("connecting"));
		socket.on("connect_error", () => this.#setStatus("disconnected"));
		socket.io.on("reconnect_attempt", () => {
			if (this.status !== "disconnected") {
				this.#setStatus("connecting");
			}
		});

		// Sent on connect, after a big change, or when asked for
		socket.on("program_state", (message: { state?: State; delta_index?: number }) => {
			this.state = message?.state ?? {};
			this.#deltaIndex = message?.delta_index;
			this.#queueState();
		});

		socket.on("program_state_update", (message: { delta_index?: number; delta?: Delta[] }) => {
			const index = message?.delta_index;
			if (typeof index !== "number" || !Array.isArray(message.delta)) {
				return;
			}
			if (this.#deltaIndex !== undefined && index <= this.#deltaIndex) {
				// Already in the state we have
				return;
			}
			if (this.#deltaIndex !== undefined && index !== this.#deltaIndex + 1) {
				// Missed an update: get the whole state again
				this.#deltaIndex = undefined;
				socket.emit("program_state", {});
				return;
			}
			try {
				applyDeltas(this.state, message.delta);
				this.#deltaIndex = index;
			} catch {
				this.#deltaIndex = undefined;
				socket.emit("program_state", {});
			}
			this.#queueState();
		});
	}

	disconnect(): void {
		if (this.#socket) {
			this.#socket.removeAllListeners();
			this.#socket.io.removeAllListeners();
			this.#socket.disconnect();
			this.#socket = undefined;
		}
		this.state = {};
		this.#deltaIndex = undefined;
		this.#setStatus("disconnected");
		this.#queueState();
	}

	/**
	 * Calls one of the web server's links, e.g. "/scoreboard1-team1-scoreup".
	 * Never throws: an unreachable HyperDrive is status 0.
	 */
	async command(path: string, init: { method?: "GET" | "POST"; body?: unknown } = {}): Promise<CommandResult> {
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), this.#timeoutMs);
		try {
			const response = await fetch(this.url + path, {
				method: init.method ?? (init.body === undefined ? "GET" : "POST"),
				headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
				body: init.body === undefined ? undefined : JSON.stringify(init.body),
				signal: controller.signal,
			});
			const body = await response.text();
			// Some actions answer 200 with an error message
			const ok = response.ok && !/^\s*ERROR\b/i.test(body);
			return { ok, status: response.status, body };
		} catch (e) {
			return { ok: false, status: 0, body: e instanceof Error ? e.message : String(e) };
		} finally {
			clearTimeout(timer);
		}
	}

	/** A GET link's JSON answer, or undefined. */
	async fetchJson<T>(path: string): Promise<T | undefined> {
		const result = await this.command(path);
		if (!result.ok) {
			return undefined;
		}
		try {
			return JSON.parse(result.body) as T;
		} catch {
			return undefined;
		}
	}

	#setStatus(status: ConnectionStatus): void {
		if (status !== this.status) {
			this.status = status;
			this.emit("status", status);
			this.#queueState();
		}
	}

	#queueState(): void {
		if (!this.#stateQueued) {
			this.#stateQueued = true;
			setImmediate(() => {
				this.#stateQueued = false;
				this.emit("state");
			});
		}
	}
}
