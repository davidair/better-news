import subprocess
import time
import requests
import platform
import psutil
import sys


class OllamaWrapper:
    def __init__(self, model='llama3'):
        self.model = model
        self.started_here = False
        self.process = None

    def is_ollama_running(self):
        try:
            requests.get("http://localhost:11434", timeout=1)
            return True
        except requests.RequestException:
            return False

    def start_ollama(self):
        if self.is_ollama_running():
            print("Ollama already running.")
            return

        print("Starting Ollama...")
        creationflags = 0
        if platform.system() == 'Windows':
            creationflags = subprocess.CREATE_NO_WINDOW  # Hide the window

        self.process = subprocess.Popen(
            ["ollama", "serve"],
            creationflags=creationflags if platform.system() == 'Windows' else 0
        )

        self.started_here = True
        time.sleep(2)  # Give server a moment to start

    def stop_ollama(self):
        if not self.started_here:
            print("Not stopping Ollama since we didn't start it.")
            return

        print("Stopping Ollama...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'ollama' in proc.info['name'] or (
                        proc.info['cmdline'] and 'ollama' in proc.info['cmdline'][0]):
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def generate(self, prompt, options):
        from ollama import Client
        client = Client()
        response = client.generate(model=self.model, prompt=prompt, options=options)
        return response['response']

    def run_inference(self, prompt, options = {}):
        try:
            self.start_ollama()
            return self.generate(prompt, options)
        finally:
            self.stop_ollama()


def main(args):
    wrapper = OllamaWrapper(model="llama3.2")
    prompt = " ".join(
        args) if args else "Explain why the sky is blue in one paragraph."
    response = wrapper.run_inference(prompt)
    print("Model response:\n", response)


if __name__ == "__main__":
    main(sys.argv[1:])
