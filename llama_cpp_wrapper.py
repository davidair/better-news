import subprocess
import time
import requests
import platform
import psutil
import sys
import yaml

from pathlib import Path


class LlamaCppWrapper:
    def __init__(self):

        script_dir = Path(__file__).resolve().parent
        config_path = script_dir / "llama-cpp-config.yaml"

        if not config_path.exists():
            raise Exception(f"Cannot find {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        self.server_path = data["server_path"]
        self.model_path = data["model_path"]
        self.started_here = False
        self.process = None

    def _is_client_running(self):
        try:
            requests.get("http://localhost:8080", timeout=1)
            return True
        except requests.RequestException:
            return False

    def start(self):
        if self._is_client_running():
            print("Server already already running.")
            return

        print("Starting llama-cpp-server...")
        creationflags = 0
        if platform.system() == 'Windows':
            creationflags = subprocess.CREATE_NO_WINDOW  # Hide the window

        self.process = subprocess.Popen(
            [self.server_path, "-m", self.model_path],
            creationflags=creationflags if platform.system() == 'Windows' else 0
        )

        self.started_here = True
        time.sleep(2)  # Give server a moment to start

    def stop(self):
        if not self.started_here:
            print("Not stopping server since we didn't start it.")
            return

        print("Stopping server...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'llama-server' in proc.info['name'] or (
                        proc.info['cmdline'] and 'ollama' in proc.info['cmdline'][0]):
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def generate(self, prompt, options):
        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:8080/v1", api_key="nocare")
        temperature = None
        if "temperature" in options:
            temperature = options["temperature"]
        response = client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content

    def run_inference(self, prompt, options={}):
        try:
            self.start()
            return self.generate(prompt, options)
        finally:
            self.stop()


def main(args):
    wrapper = LlamaCppWrapper()
    prompt = " ".join(
        args) if args else "Explain why the sky is blue in one paragraph."
    response = wrapper.run_inference(prompt)
    print("Model response:\n", response)


if __name__ == "__main__":
    main(sys.argv[1:])
