import azure.cognitiveservices.speech as sdk
from pydub import AudioSegment
import io
from xml.sax.saxutils import escape as escape_xml


class AzureVoiceService:
    def __init__(self, api_key=None, region=None):
        self.api_key = api_key
        self.region = region

    def tts(self, text, voice_name='zh-CN-YunzeNeural', language='zh-CN'):
        """
        :param text: text to be synthesized
        :return: mp3 bytes
        """

        speech_config = sdk.SpeechConfig(
            subscription=self.api_key, region=self.region)
        speech_config.speech_synthesis_language = language
        speech_config.speech_synthesis_voice_name = voice_name
        speech_config.set_speech_synthesis_output_format(
            sdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)

        synthesizer = sdk.SpeechSynthesizer(
            speech_config, audio_config=None)

        ssml = f"""
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{language}">
    <voice name="{voice_name}">
        <mstts:express-as style="calm" styledegree="2" role="SeniorMale">
            {escape_xml(text)}
        </mstts:express-as>
    </voice>
</speak>
"""

        print(f"tts start: {ssml}")

        result = synthesizer.speak_ssml(ssml)
        if result.reason != sdk.ResultReason.SynthesizingAudioCompleted:
            print(
                f"text to speech failed: {result.reason}: {result.cancellation_details.error_details}")
            return None
        return result.audio_data

    def stt(self, audio, language='zh-CN'):
        """
        :param audio: mp3 bytes
        :return: text
        """
        audio_wav_buffer = io.BytesIO()
        AudioSegment.from_file(io.BytesIO(audio)).set_sample_width(2).set_frame_rate(16000).export(
            audio_wav_buffer, format='wav')

        stream = sdk.audio.PushAudioInputStream(sdk.audio.AudioStreamFormat())
        stream.write(audio_wav_buffer.getvalue())
        stream.close()
        audio_config = sdk.AudioConfig(stream=stream)

        speech_config = sdk.SpeechConfig(
            subscription=self.api_key, region=self.region)
        speech_config.speech_recognition_language = language

        result = sdk.SpeechRecognizer(
            speech_config, audio_config=audio_config).recognize_once()
        if result.reason != sdk.ResultReason.RecognizedSpeech:
            print(
                f"speech to text failed: {result.reason}: {result.no_match_details.reason}")
            return None
        print(f"speech to text: {result.text}")
        return result.text
