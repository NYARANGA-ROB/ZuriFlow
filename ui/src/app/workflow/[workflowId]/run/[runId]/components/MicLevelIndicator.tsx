"use client";

import { Mic } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface MicLevelIndicatorProps {
    stream: MediaStream | null;
    className?: string;
}

export function MicLevelIndicator({ stream, className }: MicLevelIndicatorProps) {
    const [level, setLevel] = useState(0);
    const [isSilent, setIsSilent] = useState(false);
    const rafRef = useRef<number | null>(null);

    useEffect(() => {
        if (!stream) {
            setLevel(0);
            setIsSilent(false);
            return;
        }

        const audioTrack = stream.getAudioTracks()[0];
        if (!audioTrack) {
            return;
        }

        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);

        const data = new Uint8Array(analyser.frequencyBinCount);
        let silentSamples = 0;

        const tick = () => {
            analyser.getByteFrequencyData(data);
            const average = data.reduce((sum, value) => sum + value, 0) / data.length;
            const normalized = Math.min(100, Math.round((average / 128) * 100));
            setLevel(normalized);

            if (normalized < 2) {
                silentSamples += 1;
            } else {
                silentSamples = 0;
            }
            setIsSilent(silentSamples > 60);

            rafRef.current = requestAnimationFrame(tick);
        };

        rafRef.current = requestAnimationFrame(tick);

        return () => {
            if (rafRef.current !== null) {
                cancelAnimationFrame(rafRef.current);
            }
            source.disconnect();
            void audioContext.close();
        };
    }, [stream]);

    if (!stream) {
        return null;
    }

    return (
        <div className={className}>
            <div className="flex items-center gap-2">
                <Mic className="h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                        className="h-full rounded-full bg-emerald-500 transition-[width] duration-75"
                        style={{ width: `${level}%` }}
                    />
                </div>
                <span className="w-8 text-right text-xs tabular-nums text-muted-foreground">
                    {level}%
                </span>
            </div>
            {isSilent ? (
                <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                    No mic input detected. Check your microphone and speak louder.
                </p>
            ) : null}
        </div>
    );
}
