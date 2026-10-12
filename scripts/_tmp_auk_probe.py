from gradio_client import Client, handle_file
import shutil, time

c = Client("http://127.0.0.1:8065")
audio = handle_file("/srv/containers/edq/projects/AuK/assets/demo-input-audio/emotion-edit/en-1-input.wav")
t0 = time.time()
result = c.predict(
    False,  # use_pe=False to avoid depending on Ollama chat endpoint
    "AuK (Base)",
    audio,
    "Make the voice sound happier and more excited.",
    6,
    32,
    2.0,
    42,
    api_name="/run_generate_with_pe",
)
print("elapsed", time.time() - t0)
print("result", result)
dest = "/home/edq/ai_generated/test-artifacts/api-responses/auk_overnight_test.wav"
shutil.copy(result, dest)
print("saved to", dest)
