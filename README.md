

INSTALLATON:

1. install Python 3.10.11
2. git clone https://github.com/attyru/ya_cloud_api_demo
3. pip install yandex-speechkit pyaudiowpatch argparse grpcio
4. cd ./ya_cloud_api_demo
5. python -m main --secret your_yandex_api_key_here

USE:
1. select output device from list.
2. u can view recognised text from audio out in console, gui widget, and logfile.

CL args: --secret your_API_key_or_IAM_token --log path_2_log_file_4_recognized_text_def_./recognition_log.txt --duration session_duration_in_seconds_def_300