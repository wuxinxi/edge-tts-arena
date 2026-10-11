"""仅依赖现有 NumPy 的统一输出变速，使用相位声码器保留音高。"""

import numpy as np


def stretch_audio(audio, rate):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if rate == 1 or audio.size == 0:
        return audio
    if not np.isfinite(rate) or not 0.5 <= rate <= 2:
        raise ValueError('输出变速必须在 0.5 到 2 之间。')
    size, hop = 2048, 512
    target_length = max(1, round(len(audio) / rate))
    window = np.hanning(size + 1)[:-1].astype(np.float32)
    padded = np.pad(audio, (size // 2, size // 2), mode='reflect' if len(audio) > 1 else 'edge')
    frames = np.lib.stride_tricks.sliding_window_view(padded, size)[::hop]
    spectrum = np.fft.rfft(frames * window, axis=1).T
    times = np.arange(0, spectrum.shape[1], rate)
    spectrum = np.pad(spectrum, ((0, 0), (0, 2)))
    phase = np.angle(spectrum[:, 0])
    phase_advance = np.arange(size // 2 + 1) * (2 * np.pi * hop / size)
    output_size = size + hop * max(0, len(times) - 1)
    output = np.zeros(output_size, dtype=np.float64)
    normalizer = np.zeros(output_size, dtype=np.float64)
    window_squared = window ** 2
    for index, time in enumerate(times):
        left = int(time)
        fraction = time - left
        pair = spectrum[:, left:left + 2]
        magnitude = (1 - fraction) * np.abs(pair[:, 0]) + fraction * np.abs(pair[:, 1])
        frame = np.fft.irfft(magnitude * np.exp(1j * phase), n=size) * window
        start = index * hop
        output[start:start + size] += frame
        normalizer[start:start + size] += window_squared
        difference = np.angle(pair[:, 1]) - np.angle(pair[:, 0]) - phase_advance
        difference -= 2 * np.pi * np.round(difference / (2 * np.pi))
        phase += phase_advance + difference
    nonzero = normalizer > 1e-8
    output[nonzero] /= normalizer[nonzero]
    output = output[size // 2:size // 2 + target_length]
    if len(output) < target_length:
        output = np.pad(output, (0, target_length - len(output)))
    return output.astype(np.float32)
