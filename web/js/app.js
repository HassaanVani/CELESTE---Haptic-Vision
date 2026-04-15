/**
 * App — main controller that wires Camera, FrameProcessor, and ArduinoConnection
 * together in a requestAnimationFrame render loop.
 */
(function () {
    'use strict';

    // ── DOM refs ───────────────────────────────────
    const video        = document.getElementById('video');
    const camCanvas    = document.getElementById('camera-canvas');
    const gridOverlay  = document.getElementById('grid-overlay');
    const motorCanvas  = document.getElementById('motor-canvas');
    const btnStart     = document.getElementById('btn-start');
    const btnStop      = document.getElementById('btn-stop');
    const settingsBtn  = document.getElementById('settings-btn');
    const settingsOver = document.getElementById('settings-overlay');
    const settingsClose= document.getElementById('settings-close');
    const btnConnect   = document.getElementById('btn-connect');
    const connStatus   = document.getElementById('connection-status');
    const statusText   = document.getElementById('status-text');
    const cameraSelect = document.getElementById('camera-select');

    // Stat displays
    const statFps     = document.getElementById('stat-fps');
    const statHz      = document.getElementById('stat-hz');
    const statLatency = document.getElementById('stat-latency');
    const statFrames  = document.getElementById('stat-frames');

    // Settings inputs
    const inpIp    = document.getElementById('arduino-ip');
    const inpPort  = document.getElementById('arduino-port');
    const inpGamma = document.getElementById('gamma');
    const inpFloor = document.getElementById('brightness-floor');
    const inpCeil  = document.getElementById('brightness-ceil');
    const inpHz    = document.getElementById('update-rate');

    // ── Objects ────────────────────────────────────
    const camera     = new Camera(video);
    const processor  = new FrameProcessor();
    const connection = new ArduinoConnection();

    // ── State ──────────────────────────────────────
    let running = false;
    let rafId = null;
    let frameCount = 0;
    let sendCount = 0;
    let lastFpsTime = performance.now();
    let lastSendTime = 0;
    let fpsDisplay = 0;
    let hzDisplay = 0;
    let targetIntervalMs = 1000 / 20;  // 20 Hz default
    let lastGrid = null;

    // Canvas contexts
    const camCtx   = camCanvas.getContext('2d');
    const gridCtx  = gridOverlay.getContext('2d');
    const motorCtx = motorCanvas.getContext('2d');

    // ── Settings wiring ────────────────────────────
    settingsBtn.addEventListener('click', () => settingsOver.classList.remove('hidden'));
    settingsClose.addEventListener('click', () => settingsOver.classList.add('hidden'));
    settingsOver.addEventListener('click', (e) => {
        if (e.target === settingsOver) settingsOver.classList.add('hidden');
    });

    function bindSlider(input, display, onChange) {
        input.addEventListener('input', () => {
            display.textContent = input.value;
            if (onChange) onChange(parseFloat(input.value));
        });
    }

    bindSlider(inpGamma, document.getElementById('gamma-val'),
        v => processor.updateConfig({ gamma: v }));
    bindSlider(inpFloor, document.getElementById('floor-val'),
        v => processor.updateConfig({ brightnessFloor: v }));
    bindSlider(inpCeil, document.getElementById('ceil-val'),
        v => processor.updateConfig({ brightnessCeil: v }));
    bindSlider(inpHz, document.getElementById('hz-val'),
        v => { targetIntervalMs = 1000 / v; });

    btnConnect.addEventListener('click', async () => {
        connection.updateAddress(inpIp.value.trim(), parseInt(inpPort.value, 10));
        const status = await connection.checkStatus();
        updateConnectionUI();
        if (!status) alert('Could not reach Arduino at ' + connection.baseUrl);
    });

    // ── Camera list ────────────────────────────────
    Camera.listDevices().then(devices => {
        cameraSelect.innerHTML = '';
        if (devices.length === 0) {
            cameraSelect.innerHTML = '<option value="">No cameras found</option>';
            return;
        }
        devices.forEach((d, i) => {
            const opt = document.createElement('option');
            opt.value = d.deviceId;
            opt.textContent = d.label || ('Camera ' + (i + 1));
            cameraSelect.appendChild(opt);
        });
    });

    // ── Start / Stop ───────────────────────────────
    btnStart.addEventListener('click', startPipeline);
    btnStop.addEventListener('click', stopPipeline);

    async function startPipeline() {
        try {
            const deviceId = cameraSelect.value || undefined;
            await camera.start(deviceId);
        } catch (err) {
            alert('Camera error: ' + err.message);
            return;
        }

        // Size canvases to camera resolution
        camCanvas.width  = gridOverlay.width  = camera.width;
        camCanvas.height = gridOverlay.height = camera.height;

        // Motor canvas fixed size
        motorCanvas.width = 320;
        motorCanvas.height = 200;

        running = true;
        frameCount = 0;
        sendCount = 0;
        lastFpsTime = performance.now();
        btnStart.classList.add('hidden');
        btnStop.classList.remove('hidden');

        tick();
    }

    function stopPipeline() {
        running = false;
        if (rafId) cancelAnimationFrame(rafId);
        camera.stop();
        btnStop.classList.add('hidden');
        btnStart.classList.remove('hidden');

        // Clear canvases
        camCtx.clearRect(0, 0, camCanvas.width, camCanvas.height);
        gridCtx.clearRect(0, 0, gridOverlay.width, gridOverlay.height);
        motorCtx.clearRect(0, 0, motorCanvas.width, motorCanvas.height);

        statFps.textContent = '--';
        statHz.textContent = '--';
        statLatency.textContent = '--';
    }

    // ── Render loop ────────────────────────────────
    function tick() {
        if (!running) return;
        rafId = requestAnimationFrame(tick);

        // Draw live preview
        const raw = camera.captureRaw();
        camCtx.putImageData(raw, 0, 0);

        // Process frame for motor grid
        const blurred = camera.captureFrame();
        const grid = processor.process(blurred);
        lastGrid = grid;
        frameCount++;

        // Draw grid overlay on camera
        drawGridOverlay(grid);

        // Draw motor visualization
        drawMotorGrid(grid);

        // Send to Arduino at target rate
        const now = performance.now();
        if (now - lastSendTime >= targetIntervalMs) {
            lastSendTime = now;
            sendCount++;
            connection.sendMotorData(grid);
        }

        // Update stats every 500ms
        if (now - lastFpsTime >= 500) {
            const elapsed = (now - lastFpsTime) / 1000;
            fpsDisplay = Math.round(frameCount / elapsed);
            hzDisplay = Math.round(sendCount / elapsed);
            frameCount = 0;
            sendCount = 0;
            lastFpsTime = now;

            statFps.textContent = fpsDisplay;
            statHz.textContent = hzDisplay;
            statLatency.textContent = connection.latency ? connection.latency + 'ms' : '--';
            statFrames.textContent = parseInt(statFrames.textContent, 10) + fpsDisplay;

            updateConnectionUI();
        }
    }

    // ── Visualisation: grid overlay on camera ──────
    function drawGridOverlay(grid) {
        const w = gridOverlay.width;
        const h = gridOverlay.height;
        const rows = processor.gridRows;
        const cols = processor.gridCols;
        const zw = w / cols;
        const zh = h / rows;

        gridCtx.clearRect(0, 0, w, h);

        // Zone tint
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const val = grid[r * cols + c];
                const alpha = (val / 255) * 0.35;
                gridCtx.fillStyle = `rgba(0, 212, 170, ${alpha})`;
                gridCtx.fillRect(c * zw, r * zh, zw, zh);
            }
        }

        // Grid lines
        gridCtx.strokeStyle = 'rgba(0, 212, 170, 0.4)';
        gridCtx.lineWidth = 1;
        for (let r = 0; r <= rows; r++) {
            gridCtx.beginPath();
            gridCtx.moveTo(0, r * zh);
            gridCtx.lineTo(w, r * zh);
            gridCtx.stroke();
        }
        for (let c = 0; c <= cols; c++) {
            gridCtx.beginPath();
            gridCtx.moveTo(c * zw, 0);
            gridCtx.lineTo(c * zw, h);
            gridCtx.stroke();
        }

        // Percentage labels
        gridCtx.font = '11px Consolas, monospace';
        gridCtx.textAlign = 'center';
        gridCtx.textBaseline = 'middle';
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const val = grid[r * cols + c];
                const pct = Math.round((val / 255) * 100);
                gridCtx.fillStyle = val > 128 ? '#000' : 'rgba(255,255,255,0.8)';
                gridCtx.fillText(pct + '%', c * zw + zw / 2, r * zh + zh / 2);
            }
        }
    }

    // ── Visualisation: motor intensity circles ─────
    function drawMotorGrid(grid) {
        const W = motorCanvas.width;
        const H = motorCanvas.height;
        const rows = processor.gridRows;
        const cols = processor.gridCols;
        const padX = 30, padY = 8;
        const cellW = (W - padX * 2) / cols;
        const cellH = (H - padY * 2) / rows;
        const maxR = Math.min(cellW, cellH) * 0.4;

        motorCtx.clearRect(0, 0, W, H);

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const val = grid[r * cols + c];
                const intensity = val / 255;
                const cx = padX + c * cellW + cellW / 2;
                const cy = padY + r * cellH + cellH / 2;

                // Ring outline
                motorCtx.beginPath();
                motorCtx.arc(cx, cy, maxR, 0, Math.PI * 2);
                motorCtx.strokeStyle = '#2a2a3e';
                motorCtx.lineWidth = 1.5;
                motorCtx.stroke();

                if (intensity > 0.01) {
                    // Glow
                    if (intensity > 0.4) {
                        motorCtx.beginPath();
                        motorCtx.arc(cx, cy, maxR * 1.2, 0, Math.PI * 2);
                        const glow = motorCtx.createRadialGradient(cx, cy, maxR * 0.3, cx, cy, maxR * 1.2);
                        glow.addColorStop(0, `rgba(0, 212, 170, ${intensity * 0.3})`);
                        glow.addColorStop(1, 'rgba(0, 212, 170, 0)');
                        motorCtx.fillStyle = glow;
                        motorCtx.fill();
                    }

                    // Filled circle scaled by intensity
                    motorCtx.beginPath();
                    motorCtx.arc(cx, cy, maxR * intensity, 0, Math.PI * 2);
                    const g = Math.round(180 + 75 * intensity);
                    motorCtx.fillStyle = `rgb(0, ${g}, ${Math.round(170 * intensity)})`;
                    motorCtx.fill();
                }
            }
        }
    }

    // ── Connection UI ──────────────────────────────
    function updateConnectionUI() {
        if (connection.connected) {
            connStatus.className = 'status connected';
            statusText.textContent = 'Connected';
        } else {
            connStatus.className = 'status disconnected';
            statusText.textContent = 'Disconnected';
        }
    }

})();
