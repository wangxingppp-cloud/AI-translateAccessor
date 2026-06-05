/**
 * WASAPI Loopback Capture using NAudio.
 * Captures system audio output → resamples to 16kHz mono → stdout.
 *
 * Build: dotnet publish -c Release -o ./publish
 */
using NAudio.Wave;

try
{
    using var capture = new WasapiLoopbackCapture();

    // Buffer captured data, feed to resampler
    var buffered = new BufferedWaveProvider(capture.WaveFormat)
    {
        DiscardOnBufferOverflow = true,
    };

    // Resample to 16kHz mono 16-bit
    var outFormat = new WaveFormat(16000, 1);
    using var resampler = new MediaFoundationResampler(buffered, outFormat);
    resampler.ResamplerQuality = 60;

    var stdout = Console.OpenStandardOutput();
    var buf = new byte[outFormat.AverageBytesPerSecond / 5]; // 200ms

    capture.DataAvailable += (_, args) =>
    {
        buffered.AddSamples(args.Buffer, 0, args.BytesRecorded);

        int read;
        while ((read = resampler.Read(buf, 0, buf.Length)) > 0)
        {
            stdout.Write(buf, 0, read);
            stdout.Flush();
        }
    };

    capture.RecordingStopped += (_, _) => Environment.Exit(0);
    capture.StartRecording();

    var mre = new ManualResetEvent(false);
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; mre.Set(); };
    mre.WaitOne();
}
catch (Exception ex)
{
    Console.Error.WriteLine($"WASAPI error: {ex.Message}");
    Environment.Exit(1);
}
