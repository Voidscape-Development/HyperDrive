// HyperDrive's address (plugin-wide settings), added to every property
// inspector, with whether the plugin is connected to it.
(function () {
	const client = SDPIComponents.streamDeckClient;

	function addConnection() {
		const section = document.createElement("div");
		section.innerHTML = `
			<hr class="hd-separator">
			<sdpi-item label="__MSG_address__">
				<sdpi-textfield setting="host" global placeholder="localhost"></sdpi-textfield>
			</sdpi-item>
			<sdpi-item label="__MSG_port__">
				<sdpi-textfield setting="port" global placeholder="5500" pattern="[0-9]*"></sdpi-textfield>
			</sdpi-item>
			<sdpi-item label="__MSG_status__">
				<span class="hd-status" data-status="connecting">…</span>
			</sdpi-item>`;
		document.body.appendChild(section);
	}

	function showStatus(payload) {
		const el = document.querySelector(".hd-status");
		if (el && payload && payload.event === "status") {
			el.dataset.status = payload.status;
			el.textContent = payload.message;
		}
	}

	client.sendToPropertyInspector.subscribe((message) => showStatus(message.payload));

	// Items only used in some modes: <sdpi-item data-when="command=rps,win"
	// data-default="undo">, data-default being the setting's default value
	let settings = {};
	function showWhen() {
		for (const el of document.querySelectorAll("[data-when]")) {
			const [key, values] = el.dataset.when.split("=");
			const value = settings[key] ?? el.dataset.default;
			el.style.display = values.split(",").includes(String(value)) ? "" : "none";
		}
	}
	client.didReceiveSettings.subscribe((message) => {
		settings = message.payload.settings || {};
		showWhen();
	});
	// Settings changed here are saved, not received
	const setSettings = client.setSettings.bind(client);
	client.setSettings = (value) => {
		settings = value || {};
		showWhen();
		return setSettings(value);
	};

	document.addEventListener("DOMContentLoaded", () => {
		// Plain text outside the components: <p data-msg="key">
		for (const el of document.querySelectorAll("[data-msg]")) {
			el.textContent = SDPIComponents.i18n.getMessage(el.dataset.msg) || el.textContent;
		}
		addConnection();
		showWhen();
		client.send("sendToPlugin", { event: "status" });
	});

	const style = document.createElement("style");
	style.textContent = `
		.hd-separator { border: 0; border-top: 1px solid #444; margin: 12px 0 8px; }
		.hd-status { display: inline-block; padding: 4px 0; font-size: 9pt; }
		.hd-status[data-status="connected"] { color: #4ade80; }
		.hd-status[data-status="connecting"] { color: #facc15; }
		.hd-status[data-status="disconnected"] { color: #f87171; }
		.hd-hint { color: #969696; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; font-size: 9pt; line-height: 1.4; margin: 6px 0 0; padding: 0 12px; }
	`;
	document.head.appendChild(style);
})();
