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


def get_devices_list():

    with pyaudio.PyAudio() as pyaudio_obj:

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
                language_code=['auto']
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
    root.title('Recognition')
    root.attributes('-topmost', True)
    root.attributes('-alpha', 0.8)

    text_widget = scrolledtext.ScrolledText(
        root, wrap=tk.WORD, width=50, height=20)
    text_widget.grid(row=0, column=0, columnspan=2, sticky='nsew')

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
    transparency_scale.grid(row=1, column=0, columnspan=2,
                            sticky='ew', padx=5, pady=5)

    # Configure grid weights to make the layout responsive
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)

    root.geometry("600x400+100+100")
    root.resizable(True, True)

    threading.Thread(target=run, args=(secret, session_duration,
                     log_file, wrapped_update_callback, device)).start()

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
    parser.add_argument('--list', type=bool, default=False,
                        help='Only print list of available devices')
    args = parser.parse_args()

    if args.list:
        get_devices_list()
    else:
        create_and_update_widget(
            run, args.secret, args.duration, args.log, args.device)
