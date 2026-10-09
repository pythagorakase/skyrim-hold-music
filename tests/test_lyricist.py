import io
import json
import unittest
from unittest.mock import Mock, patch
import urllib.error

from hold_music.lyricist import MODEL, parse_lyrics, write_lyrics
from hold_music import lyria_client

RESPONSE = 'Title: The Painted Cup\nLyrics:\n[Verse]\nA painted cup returns today.\n[Chorus]\nLet clay remember, come what may.\n[Verse]\nThe kiln is warm, the wheel is slow.'


class LyricistTests(unittest.TestCase):
    def test_prompt_and_result(self):
        client = Mock()
        client.chat_completion.return_value = dict(content=RESPONSE, request_id='lyric-test', usage={'cost': .001})
        brief = dict(summary='An invented potter recovered a cup.', evidence='rumor',
                     factual_framing='This is hearsay.', topic_id='evt:21', tradition='whiterun')
        result = write_lyrics(brief, performer={'name': 'Synthetic Bard', 'venue': 'Imaginary Inn'},
                              region_label='Whiterun', gender='male', client=client, model='test/model')
        self.assertEqual(result, dict(title='The Painted Cup', lyrics=RESPONSE.split('Lyrics:\n')[1],
                                     model='test/model', request_id='lyric-test', usage={'cost': .001}))
        args = client.chat_completion.call_args.kwargs
        self.assertEqual(args['model'], 'test/model')
        prompt = '\n'.join(m['content'] for m in args['messages'])
        for value in (brief['summary'], 'hearsay', 'Synthetic Bard', 'Imaginary Inn', 'Whiterun',
                      'male', '[Verse]', '[Chorus]', '200 words', 'Never name', 'quest outcome'):
            self.assertIn(value, prompt)
        self.assertNotIn('HM1[', prompt)
        self.assertNotIn('Style:', prompt)
        client.chat_completion.assert_called_once()
        self.assertEqual(MODEL, 'openai/gpt-5.6-terra')

    def test_rejections(self):
        for content in ('Lyrics: missing title', 'Title: missing lyrics',
                        'Title: \nLyrics: x', 'Title: x\nLyrics:',
                        'Title: x\nLyrics: ' + 'x' * 1201,
                        RESPONSE + '\nHM1[bad]', RESPONSE + '\nStyle: bad', None):
            with self.subTest(content=content), self.assertRaises(ValueError):
                parse_lyrics(content)

    def test_character_boundary(self):
        self.assertEqual(len(parse_lyrics('Title: x\nLyrics: ' + 'x' * 1200)[1]), 1200)

    def test_transport_nonstreaming_request_and_key_reader(self):
        response = Mock()
        response.status = 200
        response.headers = {'X-Request-ID': 'header-id'}
        response.read.return_value = json.dumps(dict(id='provider-id', usage={'cost': .002},
            choices=[{'message': {'content': RESPONSE}}])).encode()
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch.object(lyria_client.urllib.request, 'build_opener', return_value=opener), \
                patch.object(lyria_client, 'read_openrouter_key', return_value='synthetic-key') as key:
            result = lyria_client.chat_completion([{'role': 'user', 'content': 'invented'}],
                                                 model=MODEL, bardsinging_yaml_path='fixture.yaml')
        key.assert_called_once_with('fixture.yaml')
        request = opener.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertIs(payload['stream'], False)
        self.assertEqual(payload['model'], MODEL)
        self.assertEqual(result['request_id'], 'provider-id')
        self.assertEqual(result['content'], RESPONSE)
        self.assertEqual(response.read.call_args.args, (1_000_001,))
        opener.open.assert_called_once()

    def test_transport_errors_are_body_free_and_not_retried(self):
        for failure, expected in [(OSError('PRIVATE'), lyria_client.StreamError),
                (urllib.error.HTTPError('synthetic', 429, 'PRIVATE', {}, io.BytesIO(b'PRIVATE')),
                 lyria_client.HTTPStatusError)]:
            opener = Mock()
            opener.open.side_effect = failure
            with patch.object(lyria_client.urllib.request, 'build_opener', return_value=opener), \
                    self.assertRaises(expected) as error:
                lyria_client.chat_completion([], model=MODEL, key='synthetic')
            self.assertNotIn('PRIVATE', str(error.exception))
            opener.open.assert_called_once()

    def test_invalid_and_oversized_transport_responses(self):
        for body, error_type in [(b'PRIVATE invalid JSON', lyria_client.StreamError),
                                (b'{}', lyria_client.StreamError),
                                (b'x' * 1_000_001, lyria_client.ResponseTooLargeError)]:
            response = Mock(status=200, headers={})
            response.read.return_value = body
            opener = Mock()
            opener.open.return_value.__enter__ = Mock(return_value=response)
            opener.open.return_value.__exit__ = Mock(return_value=False)
            with patch.object(lyria_client.urllib.request, 'build_opener', return_value=opener), \
                    self.assertRaises(error_type) as error:
                lyria_client.chat_completion([], model=MODEL, key='synthetic')
            self.assertNotIn('PRIVATE', str(error.exception))
            opener.open.assert_called_once()


if __name__ == '__main__':
    unittest.main()
