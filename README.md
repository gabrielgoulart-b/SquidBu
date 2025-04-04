# Bambu Lab Printer Monitor

This project implements a web page to monitor the status of a Bambu Lab 3D printer on the local network using MQTT, with additional features including authentication and sharing.

## Features

*   **Real-time Monitoring:** Fetches printer data via MQTT.
*   **Web Interface:** Displays organized information:
    *   **Overview:** Current printer status, Wi-Fi signal.
    *   **Progress:** G-code file, current/total layer, remaining time, progress bar.
    *   **Temperatures & Fans:** Current and target nozzle/bed temperature, chamber temperature (if available), fan speeds.
    *   **AMS:** Details of each AMS unit and tray (filament type, color, estimated remaining percentage). *(Note: Interface now attempts to read `stg` array data for better AMS Lite compatibility).*
    *   **Camera:** Displays the video stream from the printer's camera (requires correct URL configuration in `config.json` and camera accessibility).
    *   **Temperature Chart:** History of nozzle, bed, and chamber temperatures.
*   **User Authentication:** Login system with username and password to protect access to the main interface. Includes a "Remember Me" option.
*   **Shareable Live View:** A special URL (`/live/<token>`) allows sharing a simplified view (progress and camera) without login, protected by a secret token. Now includes a "🔗 Share" button in the top bar for easier link copying/sending.
*   **Push Notifications:** Receive notifications on your browser or phone for important print events (start, finish, error/pause) using Web Push. Requires configuration (see below).
*   **Light/Dark Theme:** Toolbar button to toggle the visual theme, with preference saved in the browser.
*   **Responsive Layout:** The interface automatically adapts for better viewing on desktop and mobile screens (with a collapsible sidebar on mobile).
*   **Remote Access (Optional):** Can be configured via Tailscale Funnel for secure access from outside the local network.

## Structure

*   `app.py`: Python (Flask) backend that:
    *   Connects to the printer via MQTT.
    *   Implements user authentication (login/logout) using Flask-Login.
    *   Serves the main interface (`/`), login page (`/login`), and live view (`/live/<token>`).
    *   Serves the `/status` API.
    *   Acts as a proxy for the camera (`/camera_proxy`).
*   `templates/index.html`: Main frontend (requires login).
*   `templates/login.html`: Login page.
*   `templates/live_view.html`: Simplified page for shared live view.
*   `static/css/style.css`: Main stylesheet.
*   `static/js/script.js`: JavaScript for the main interface (data updates, themes, sharing, etc.).
*   `static/js/notifications.js`: JavaScript for managing push notifications.
*   `static/js/service-worker.js`: Service Worker for receiving push notifications.
*   `config.json`: Local configuration file (NOT versioned).
*   `config.json.example`: Example configuration file.
*   `requirements.txt`: Python dependencies (Flask, paho-mqtt, requests, Flask-Login, Flask-WTF, pywebpush).
*   `SquidStart.py`: Optional script to start and monitor `app.py` and `tailscale funnel` on boot via systemd.
*   `LEIAME.md`: README file in Brazilian Portuguese.
*   `.gitignore`: File to prevent unnecessary files (like `venv`, `config.json`, logs) from being committed to Git.

## Configuration

1.  **Clone the Repository (if getting from GitHub):**
    ```bash
    git clone <REPOSITORY_URL>
    cd <REPOSITORY_FOLDER>
    ```

2.  **Create the Local Configuration File:**
    *   In the project directory, copy the example file:
        ```bash
        cp config.json.example config.json
        ```
    *   Edit the new `config.json` file with a text editor (e.g., `nano config.json`).
    *   Fill in the correct values for the following keys, replacing the placeholders:
        *   `PRINTER_IP`: The IP address of your Bambu Lab printer on the local network.
        *   `ACCESS_CODE`: The LAN Access Code for your printer (found in its network settings or the Bambu Handy app).
        *   `DEVICE_ID`: The Serial Number of your printer.
        *   `CAMERA_URL`: The full URL for your camera's MJPEG stream (e.g., `http://192.168.X.Y:ZZZZ/?action=stream`). If not using, you can leave the example value.
        *   `SECRET_KEY`: A long, random secret key for Flask session security. **Important:** Generate a secure key! You can use Python:
            ```bash
            # In the terminal, run:
            python3 -c 'import secrets; print(secrets.token_hex(24))'
            # Copy the output and paste it as the key's value in the JSON.
            ```
        *   `LOGIN_USERNAME`: The username you will use to log in to the interface.
        *   `LOGIN_PASSWORD_HASH`: The password hash corresponding to the `LOGIN_USERNAME`. **DO NOT PUT THE PLAINTEXT PASSWORD HERE.** To generate the hash:
            1.  Ensure the virtual environment is active (`source venv/bin/activate`).
            2.  Run the Flask interactive shell: `flask shell`
            3.  Inside the shell, import the function and generate the hash (replace `'your_password_here'`):
                ```python
                from werkzeug.security import generate_password_hash
                print(generate_password_hash('your_password_here'))
                exit() # Exits the shell
                ```
            4.  Copy the complete output (starting with `scrypt:...` or `pbkdf2:...`) and paste it as the key's value in the JSON.
        *   `LIVE_SHARE_TOKEN` (Optional): A secret, hard-to-guess string to use in the live view URL. If not using sharing, you can leave it empty or remove the key. To generate a token:
             ```bash
             # In the terminal, run:
             python3 -c 'import secrets; print(secrets.token_hex(16))'
             # Copy the output and paste it as the key's value in the JSON.
             ```
        *   **VAPID Settings (for Push Notifications - Optional):**
            *   `VAPID_ENABLED`: Set to `true` to enable push notifications, or `false` to disable.
            *   `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_MAILTO`: Keys required for Web Push. To generate them:
                1.  Ensure the virtual environment is active (`source venv/bin/activate`).
                2.  Ensure `pywebpush` is installed (`pip install pywebpush`).
                3.  Run the Python command to generate and display the keys (adjust command if the library changes):
                    ```bash
                    python -c "import base64; from cryptography.hazmat.primitives import serialization; from pywebpush import Vapid; v = Vapid(); v.generate_keys(); pk_raw = v.public_key.public_bytes(encoding=serialization.Encoding.X962, format=serialization.PublicFormat.UncompressedPoint); sk_der = v.private_key.private_bytes(encoding=serialization.Encoding.DER, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()); print(f\"Private Key: {base64.urlsafe_b64encode(sk_der).rstrip(b'=').decode('utf-8')}\"); print(f\"Public Key (Raw): {base64.urlsafe_b64encode(pk_raw).rstrip(b'=').decode('utf-8')}\")"
                    ```
                4.  Copy the generated "Public Key (Raw)" and paste it as the value for `VAPID_PUBLIC_KEY` in `config.json`.
                5.  Copy the generated "Private Key" and paste it as the value for `VAPID_PRIVATE_KEY` in `config.json`.
                6.  Set `VAPID_MAILTO` to your email address in the format `mailto:youremail@example.com`. This is used by some push services.
    *   **Important:** The `config.json` file contains sensitive information and **will not be committed** to GitHub (it's in `.gitignore`).

3.  **Create and Activate the Virtual Environment:**
    *   Navigate to the project directory.
    *   Create the virtual environment (naming it `venv` is recommended):
        ```bash
        python3 -m venv venv
        # Activate the virtual environment:
        source venv/bin/activate  # On Linux/macOS
        # venv\Scripts\activate    # On Windows
        ```
        *Note: The `SquidStart.py` script now assumes the venv is located at `./venv`. If you use a different name/location, you'll need to adjust the `VENV_PYTHON` variable at the beginning of `SquidStart.py`.* 

4.  **Install Dependencies:**
    *   With the virtual environment active, run:
        ```bash
        pip install -r requirements.txt
        ```

## Local Execution

1.  **Ensure `config.json` exists and is correctly filled (including login keys).**

2.  **Start the backend server:**
    *   With the virtual environment active, run:
        ```bash
        python app.py
        ```
    *   If there are errors loading `config.json` or missing dependencies, messages will appear in the terminal.

3.  **Access the web page:**
    *   Open a browser on the **same local network**.
    *   Go to: `http://<IP_OF_DEVICE_RUNNING_APP>:5000` (replace with the IP of the device running the app).
    *   You will be redirected to the login page. Use the `LOGIN_USERNAME` and the password corresponding to the `LOGIN_PASSWORD_HASH` configured.

4.  **Enable Notifications (Optional):** If configured in `config.json`, click the 🔔 button in the top bar and allow notifications in your browser.

## Shareable Live View (Optional)

If you configured a `LIVE_SHARE_TOKEN` in `config.json`, you can click the "🔗 Share" button in the top bar to copy or send the special link:

`http://<IP_OF_DEVICE_RUNNING_APP>:5000/live/<YOUR_LIVE_SHARE_TOKEN>`

Or, if using Tailscale Funnel:

`https://<hostname>.<your-tailnet>.ts.net/live/<YOUR_LIVE_SHARE_TOKEN>`

*   Replace `<YOUR_LIVE_SHARE_TOKEN>` with the exact value you set in `config.json`.
*   Anyone with this link can view the simplified page without needing to log in.
*   If the token is incorrect or not configured, access will be denied.

## Remote Access (Optional - Via Tailscale Funnel)

(This section remains the same, but remember that accessing via the Tailscale URL will also require login for the main interface).

## Start on Boot ...

## Troubleshooting ... 