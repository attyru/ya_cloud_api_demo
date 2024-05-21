This is an example of using real-time voice recognition from an audio output device using the Yandex Cloud API.

INSTALLATON:

1. install Python 3.10.11
2. git clone <https://github.com/attyru/ya_cloud_api_demo>
3. pip install yandex-speechkit pyaudiowpatch argparse grpcio
4. cd ./ya_cloud_api_demo
5. python -m main --secret your_yandex_api_key_here

USE:

1. select output device from list. or view device indexes with arg --list_only True and run with arg --device N
2. u can view recognised text from audio out in console, gui widget, and logfile.

CL args: --secret your_API_key_or_IAM_token --log path_2_log_file_4_recognized_text_def_./recognition_log.txt --duration session_duration_in_seconds_def_300 --device forced_device_number_def_None --list true_or_false_def_false

Known issues:

1. The text is recognized in parts - given the previous ones, so the output looks ugly. I'm working on a fix.
2. Mixed languages are not recognized, only Russian. Done.
3. The widget does not have the ability to interactively resize the window. Done.
4. The close button on the widget does not work correctly - it closes the widget but does not terminate the process.
5. The minimize button on the widget throws an exception. Done.

Planned features:

1. Recognizing speaker identity from local samples.
2. Possibility to use Google API and engines based on openai 'whisper' library.
