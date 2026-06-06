/**
 * WASAPI Loopback → 16kHz mono 16-bit PCM → stdout
 *
 * Simple resampling: stereo→mono, downsample, 32-bit→16-bit.
 * No external resampler — just basic DSP that works reliably.
 */
using NAudio.Wave;

try
{
    using var capture = new WasapiLoopbackCapture();
    var srcRate = capture.WaveFormat.SampleRate;   // e.g. 48000
    var srcCh = capture.WaveFormat.Channels;         // e.g. 2
    var srcBits = capture.WaveFormat.BitsPerSample;  // e.g. 32

    const int outRate = 16000;
    const int outCh = 1;
    const int outBits = 16;

    // Resample ratio
    double ratio = (double)outRate / srcRate;

    var stdout = Console.OpenStandardOutput();

    capture.DataAvailable += (_, args) =>
    {
        int bytesPerSample = srcBits / 8;
        int frameSize = bytesPerSample * srcCh;
        int srcFrames = args.BytesRecorded / frameSize;
        if (srcFrames == 0) return;

        int outFrames = (int)(srcFrames * ratio);
        if (outFrames < 1) return;

        // Manual interleaved read + resample
        var outBuf = new byte[outFrames * outCh * (outBits / 8)];
        int outIdx = 0;

        for (int i = 0; i < outFrames; i++)
        {
            double srcIdx = i / ratio;
            int lo = (int)srcIdx;

            // Stereo → mono mix, then linear interpolate
            float sample;
            if (srcCh == 2 && srcBits == 32)
            {
                // Fast path: 32-bit float stereo (most common WASAPI format)
                int loOff = lo * 8; // 2ch × 4 bytes
                float l = BitConverter.ToSingle(args.Buffer, loOff);
                float r = BitConverter.ToSingle(args.Buffer, loOff + 4);
                sample = (l + r) * 0.5f; // stereo → mono
            }
            else if (srcBits == 16)
            {
                int loOff = lo * srcCh * 2;
                if (srcCh == 2)
                {
                    short l = BitConverter.ToInt16(args.Buffer, loOff);
                    short r = BitConverter.ToInt16(args.Buffer, loOff + 2);
                    sample = (l + r) * 0.5f / 32768f;
                }
                else
                {
                    sample = BitConverter.ToInt16(args.Buffer, loOff) / 32768f;
                }
            }
            else
            {
                continue; // Unsupported format
            }

            // Float → 16-bit PCM
            short pcm = (short)Math.Max(-32768, Math.Min(32767, (int)(sample * 32767f)));
            outBuf[outIdx] = (byte)(pcm & 0xFF);
            outBuf[outIdx + 1] = (byte)((pcm >> 8) & 0xFF);
            outIdx += 2;
        }

        stdout.Write(outBuf, 0, outIdx);
        stdout.Flush();
    };

    capture.RecordingStopped += (_, _) => Environment.Exit(0);
    capture.StartRecording();

    // Block forever
    var mre = new ManualResetEvent(false);
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; mre.Set(); };
    mre.WaitOne();
}
catch (Exception ex)
{
    Console.Error.WriteLine($"WASAPI: {ex.Message}");
    Environment.Exit(1);
}
