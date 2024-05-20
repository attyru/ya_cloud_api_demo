import pyaudiowpatch as pyaudio
import argparse
import grpc
import yandex.cloud.ai.stt.v3.stt_pb2 as stt_pb2
import yandex.cloud.ai.stt.v3.stt_service_pb2_grpc as stt_service_pb2_grpc
import time
import sys
import tkinter as tk
from tkinter import scrolledtext
import threading


def get_device_index(pyaudio_obj):
    devices_count = pyaudio_obj.get_device_count()
    available_devices = []

    for i in range(devices_count):
        device_info = pyaudio_obj.get_device_info_by_index(i)
        if device_info['maxOutputChannels'] > 0 and device_info['hostApi'] == pyaudio_obj.get_host_api_info_by_type(pyaudio.paWASAPI)['index'] and device_info['hostApi'] != -1:
            available_devices.append((i, device_info['name']))

    print("Available Output Devices (WASAPI):")
    for index, (device_index, device_name) in enumerate(available_devices):
        print(f"{index}: {device_name}")

    if not available_devices:
        print("No available output devices found.")
        sys.exit()

    try:
        choice = input(
            "Enter the device number to select or press Enter to select the current device: ")
        if choice == "":
            default_device_info = pyaudio_obj.get_default_output_device_info()
            return default_device_info['index']
        else:
            choice = int(choice)
            if 0 <= choice < len(available_devices):
                return available_devices[choice][0]
            else:
                raise ValueError("Invalid choice.")
    except ValueError as e:
        print(e)
        sys.exit()


def find_loopback_device(pyaudio_obj, default_speakers):
    if not default_speakers["isLoopbackDevice"]:
        for loopback in pyaudio_obj.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                return loopback
        print("Default loopback output device not found.\n\nRun `python -m pyaudiowpatch` to check available devices.\nExiting...\n")
        sys.exit()
    return default_speakers


def get_recognition_options(speakers):
    return stt_pb2.StreamingOptions(
        recognition_model=stt_pb2.RecognitionModelOptions(
            audio_format=stt_pb2.AudioFormatOptions(
                raw_audio=stt_pb2.RawAudio(
                    audio_encoding=stt_pb2.RawAudio.LINEAR16_PCM,
                    sample_rate_hertz=int(speakers["defaultSampleRate"]),
                    audio_channel_count=speakers["maxInputChannels"]
                )
            ),
            text_normalization=stt_pb2.TextNormalizationOptions(
                text_normalization=stt_pb2.TextNormalizationOptions.TEXT_NORMALIZATION_ENABLED,
                profanity_filter=False,
                literature_text=False
            ),
            language_restriction=stt_pb2.LanguageRestrictionOptions(
                restriction_type=stt_pb2.LanguageRestrictionOptions.WHITELIST,
                language_code=['ru-RU']
            ),
            audio_processing_type=stt_pb2.RecognitionModelOptions.REAL_TIME
        )
    )


def audio_generator(pyaudio_obj, device_index, session_duration):
    speakers = pyaudio_obj.get_device_info_by_index(device_index)
    speakers = find_loopback_device(pyaudio_obj, speakers)
    recognize_options = get_recognition_options(speakers)
    yield stt_pb2.StreamingRequest(session_options=recognize_options)

    print(f"Recording from: ({speakers['index']}) {speakers['name']}")

    chunk = 4096
    sample_rate = int(speakers["defaultSampleRate"])
    channels = int(speakers["maxInputChannels"])

    start_time = time.time()

    with pyaudio_obj.open(format=pyaudio.paInt16,
                          channels=channels,
                          rate=sample_rate,
                          frames_per_buffer=chunk,
                          input=True,
                          input_device_index=speakers["index"]) as stream:
        while time.time() - start_time < session_duration:
            in_data = stream.read(chunk)
            yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=in_data))


def run(secret, session_duration, log_file, update_callback, device):
    credentials = grpc.ssl_channel_credentials()
    channel = grpc.secure_channel('stt.api.cloud.yandex.net:443', credentials)
    stub = stt_service_pb2_grpc.RecognizerStub(channel)

    with pyaudio.PyAudio() as pyaudio_obj:

        if device != None:
            device_index = device
        else:
            device_index = get_device_index(pyaudio_obj)

        audio_stream = audio_generator(
            pyaudio_obj, device_index, session_duration)

        it = stub.RecognizeStreaming(audio_stream, metadata=(
            ('authorization', f'Api-Key {secret}'),))
        with open(log_file, 'w', encoding='utf-8') as log:
            try:
                for response in it:
                    event_type = response.WhichOneof('Event')
                    alternatives = None
                    if event_type == 'partial' and response.partial.alternatives:
                        alternatives = [
                            alt.text for alt in response.partial.alternatives]
                    elif event_type == 'final' and response.final.alternatives:
                        alternatives = [
                            alt.text for alt in response.final.alternatives]
                    elif event_type == 'final_refinement' and response.final_refinement.normalized_text.alternatives:
                        alternatives = [
                            alt.text for alt in response.final_refinement.normalized_text.alternatives]

                    if alternatives:
                        for alt in alternatives:
                            log.write(f'{alt}\n')
                            log.flush()
                            print(f'type={event_type}, alternatives={alt}')
                            update_callback(alt)
            except grpc._channel._MultiThreadedRendezvous as err:
                print(f'Error code {err.code()}, message: {err.details()}')
                raise


def create_and_update_widget(run, secret, session_duration, log_file, device):
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.overrideredirect(True)
    root.attributes('-alpha', 0.8)
    root.resizable(True, True)

    def close_window():
        root.destroy()
        sys.exit()

    def minimize_window():
        root.iconify()

    # Frame for the title bar with buttons
    title_bar = tk.Frame(root, bg='gray', relief='raised', bd=2)
    title_bar.pack(fill='x')

    # Add the minimize and close buttons to the right side of the title bar
    close_button = tk.Button(
        title_bar, text="X", command=close_window, bg='gray', fg='white', bd=0)
    close_button.pack(side='right')

    minimize_button = tk.Button(
        title_bar, text="_", command=minimize_window, bg='gray', fg='white', bd=0)
    minimize_button.pack(side='right')

    text_widget = scrolledtext.ScrolledText(
        root, wrap=tk.WORD, width=50, height=20)
    text_widget.pack(expand=True, fill='both')

    def on_mouse_down(event):
        root._drag_data = {'x': event.x, 'y': event.y}

    def on_mouse_move(event):
        x = root.winfo_pointerx() - root._drag_data['x']
        y = root.winfo_pointery() - root._drag_data['y']
        root.geometry(f"+{x}+{y}")

    title_bar.bind('<ButtonPress-1>', on_mouse_down)
    title_bar.bind('<B1-Motion>', on_mouse_move)

    def update_text(text):
        text_widget.insert(tk.END, text + '\n')
        text_widget.see(tk.END)

    def wrapped_update_callback(text):
        root.after(0, update_text, text)

    def set_transparency(value):
        root.attributes('-alpha', float(value))

    transparency_scale = tk.Scale(root, from_=0.2, to=1.0, resolution=0.01,
                                  orient=tk.HORIZONTAL, label='Transparency', command=set_transparency)
    transparency_scale.set(0.8)
    transparency_scale.pack()

    def on_scale_click(event):
        title_bar.unbind('<ButtonPress-1>')
        title_bar.unbind('<B1-Motion>')

    def on_scale_release(event):
        title_bar.bind('<ButtonPress-1>', on_mouse_down)
        title_bar.bind('<B1-Motion>', on_mouse_move)

    transparency_scale.bind('<ButtonPress-1>', on_scale_click)
    transparency_scale.bind('<ButtonRelease-1>', on_scale_release)

    root.geometry("600x400+100+100")

    threading.Thread(target=run, args=(secret, session_duration,
                     log_file, device, wrapped_update_callback)).start()

    root.mainloop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--secret', required=True, help='API key or IAM token')
    parser.add_argument('--duration', type=int, default=300,
                        help='Session duration in seconds')
    parser.add_argument('--log', type=str, default='recognition_log.txt',
                        help='Log file for recognized text')
    parser.add_argument('--device', type=int, default=None,
                        help='Force default device')
    args = parser.parse_args()

    create_and_update_widget(
        run, args.secret, args.duration, args.log, args.device)
