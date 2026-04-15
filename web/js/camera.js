/**
 * Camera — webcam capture via getUserMedia.
 *
 * Draws each frame to an offscreen canvas so the processor can grab ImageData.
 */
class Camera {
    constructor(videoEl) {
        this.video = videoEl;
        this.stream = null;
        this.width = 640;
        this.height = 480;

        // Offscreen canvas for pixel extraction
        this._canvas = document.createElement('canvas');
        this._ctx = this._canvas.getContext('2d', { willReadFrequently: true });
    }

    /** Enumerate available video devices for the settings dropdown. */
    static async listDevices() {
        // Trigger permission prompt so labels are populated
        try {
            const tmp = await navigator.mediaDevices.getUserMedia({ video: true });
            tmp.getTracks().forEach(t => t.stop());
        } catch (_) { /* permission denied — labels will be empty */ }

        const devices = await navigator.mediaDevices.enumerateDevices();
        return devices.filter(d => d.kind === 'videoinput');
    }

    /**
     * Start streaming from the given deviceId (or default camera).
     */
    async start(deviceId) {
        const constraints = {
            video: {
                width:  { ideal: this.width },
                height: { ideal: this.height },
                facingMode: 'environment'
            }
        };
        if (deviceId) {
            constraints.video.deviceId = { exact: deviceId };
        }

        this.stream = await navigator.mediaDevices.getUserMedia(constraints);
        this.video.srcObject = this.stream;
        await this.video.play();

        // Actual resolution may differ from requested
        this.width = this.video.videoWidth;
        this.height = this.video.videoHeight;
        this._canvas.width = this.width;
        this._canvas.height = this.height;
    }

    /**
     * Capture the current frame as ImageData.
     * Applies a light blur via CSS filter to reduce noise.
     */
    captureFrame() {
        this._ctx.filter = 'blur(2px)';
        this._ctx.drawImage(this.video, 0, 0, this.width, this.height);
        this._ctx.filter = 'none';
        return this._ctx.getImageData(0, 0, this.width, this.height);
    }

    /** Get the raw (unfiltered) frame for the live preview canvas. */
    captureRaw() {
        this._ctx.filter = 'none';
        this._ctx.drawImage(this.video, 0, 0, this.width, this.height);
        return this._ctx.getImageData(0, 0, this.width, this.height);
    }

    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
        this.video.srcObject = null;
    }
}
