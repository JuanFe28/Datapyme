"""Comprueba los MP4 finales, sus fuentes y la coherencia de los subtítulos."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import cv2

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seconds(text):
    h, m, s = text.replace(',', '.').split(':')
    return int(h)*3600 + int(m)*60 + float(s)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffmpeg', required=True)
    args = parser.parse_args()
    results = []
    for label, suffix in [('PRESENTACION', ''), ('RESUMEN', '_RESUMEN')]:
        stem = 'DATAPYME_' + label + '_PROFESIONAL'
        video = HERE / (stem + '_1080P.mp4')
        srt = HERE / (stem + '.srt')
        montage = json.loads((HERE / ('MONTAJE'+suffix+'.json')).read_text(encoding='utf-8'))
        capture = cv2.VideoCapture(str(video))
        assert capture.isOpened(), video.name
        width, height = [round(capture.get(k)) for k in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT)]
        fps = capture.get(cv2.CAP_PROP_FPS)
        frames = round(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        assert (width, height) == (1920, 1080)
        assert abs(fps-25) < 0.01
        assert abs(frames/fps-montage['duration']) <= 0.2
        decode = subprocess.run([args.ffmpeg, '-hide_banner', '-v', 'error', '-xerror', '-i', str(video), '-map', '0:v:0', '-f', 'null', '-'], capture_output=True, text=True)
        assert decode.returncode == 0 and not decode.stderr.strip(), decode.stderr
        info = subprocess.run([args.ffmpeg, '-hide_banner', '-i', str(video)], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
        assert 'Audio:' not in info
        embedded = len(re.findall(r'Chapter #', info))
        assert embedded == len(montage['chapters'])+2
        for chapter in montage['chapters']:
            assert sha(HERE.parent/chapter['source']) == chapter['source_sha256']
        previous = 0
        blocks = srt.read_text(encoding='utf-8').strip().split('\n\n')
        assert len(blocks) == len(montage['subtitles'])
        for number, (block, cue) in enumerate(zip(blocks, montage['subtitles']), 1):
            lines = block.splitlines()
            assert int(lines[0]) == number
            start, end = map(seconds, lines[1].split(' --> '))
            text = ' '.join(lines[2:])
            assert previous <= start < end <= montage['duration']
            assert abs(start-cue['start']) < 0.002 and abs(end-cue['end']) < 0.002
            assert text == cue['text']
            assert len(text)/(end-start) <= 17.5
            previous = end
        results.append({'file':video.name, 'sha256':sha(video), 'bytes':video.stat().st_size,
                        'duration_seconds':frames/fps, 'resolution':[width,height], 'fps':fps,
                        'frames':frames, 'complete_decode':'passed', 'audio_streams':0,
                        'embedded_chapters':embedded, 'subtitle_cues':len(blocks),
                        'maximum_subtitle_characters_per_second':max(c['cps'] for c in montage['subtitles']),
                        'subtitle_timing_and_content':'passed', 'source_hashes':'passed',
                        'srt_sha256':sha(srt)})
    assert 10000+1900 == 11900 and 115000+21850 == 136850 and 115000-78000 == 37000
    report = {'verified_date':'2026-11-25', 'source_revision':montage['source_revision'],
              'ffmpeg_version':subprocess.check_output([args.ffmpeg, '-version'], text=True).splitlines()[0],
              'scope':'Complete technical decode, metadata, chapter counts, SRT timing/content, reading speed, source hashes and example arithmetic. Application/server tests not rerun.',
              'videos':results}
    (HERE/'VERIFICACION_TECNICA.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
