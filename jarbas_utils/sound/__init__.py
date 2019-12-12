import subprocess
from jarbas_utils.log import LOG


def play_audio(uri, play_cmd="play %1"):
    """ Play a audio file.

        Returns: subprocess.Popen object
    """
    play_wav_cmd = str(play_cmd).split(" ")
    for index, cmd in enumerate(play_wav_cmd):
        if cmd == "%1":
            play_wav_cmd[index] = uri
    try:
        return subprocess.Popen(play_wav_cmd)
    except Exception as e:
        LOG.error("Failed to launch WAV: {}".format(play_wav_cmd))
        LOG.debug("Error: {}".format(repr(e)), exc_info=True)
        return None


def play_wav(uri, play_cmd="paplay %1"):
    """ Play a wav-file.

        Returns: subprocess.Popen object
    """
    play_wav_cmd = str(play_cmd).split(" ")
    for index, cmd in enumerate(play_wav_cmd):
        if cmd == "%1":
            play_wav_cmd[index] = uri
    try:
        return subprocess.Popen(play_wav_cmd)
    except Exception as e:
        LOG.error("Failed to launch WAV: {}".format(play_wav_cmd))
        LOG.debug("Error: {}".format(repr(e)), exc_info=True)
        return None


def play_mp3(uri, play_cmd="mpg123 %1"):
    """ Play a mp3-file.

        Returns: subprocess.Popen object
    """
    play_mp3_cmd = str(play_cmd).split(" ")
    for index, cmd in enumerate(play_mp3_cmd):
        if cmd == "%1":
            play_mp3_cmd[index] = uri
    try:
        return subprocess.Popen(play_mp3_cmd)
    except Exception as e:
        LOG.error("Failed to launch MP3: {}".format(play_mp3_cmd))
        LOG.debug("Error: {}".format(repr(e)), exc_info=True)
        return None


def play_ogg(uri, play_cmd="ogg123 -q %1"):
    """ Play a ogg-file.

        Returns: subprocess.Popen object
    """
    play_ogg_cmd = str(play_cmd).split(" ")
    for index, cmd in enumerate(play_ogg_cmd):
        if cmd == "%1":
            play_ogg_cmd[index] = uri
    try:
        return subprocess.Popen(play_ogg_cmd)
    except Exception as e:
        LOG.error("Failed to launch OGG: {}".format(play_ogg_cmd))
        LOG.debug("Error: {}".format(repr(e)), exc_info=True)
        return None


def record(file_path, duration, rate, channels):
    if duration > 0:
        return subprocess.Popen(
            ["arecord", "-r", str(rate), "-c", str(channels), "-d",
             str(duration), file_path])
    else:
        return subprocess.Popen(
            ["arecord", "-r", str(rate), "-c", str(channels), file_path])

