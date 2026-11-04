"use client";

import { Loader2, Mic, Phone, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { RealtimeFeedback } from "@/components/workflow/conversation";

import {
    ApiKeyErrorDialog,
    ConnectionStatus,
    MicLevelIndicator,
    WorkflowConfigErrorDialog,
} from "../../run/[runId]/components";
import { useWebSocketRTC } from "../../run/[runId]/hooks";
import type { WorkflowRuntimeNodeTransition } from "./types";

interface EmbeddedVoiceTesterProps {
    workflowId: number;
    workflowRunId: number;
    initialContextVariables?: Record<string, string>;
    accessToken: string;
    onRequestNewRun: () => Promise<void>;
    onNodeTransition?: (transition: WorkflowRuntimeNodeTransition) => void;
}

export function EmbeddedVoiceTester({
    workflowId,
    workflowRunId,
    initialContextVariables,
    accessToken,
    onRequestNewRun,
    onNodeTransition,
}: EmbeddedVoiceTesterProps) {
    const router = useRouter();
    const {
        audioRef,
        audioInputs,
        selectedAudioInput,
        setSelectedAudioInput,
        connectionActive,
        permissionError,
        isCompleted,
        apiKeyModalOpen,
        setApiKeyModalOpen,
        apiKeyError,
        apiKeyErrorCode,
        workflowConfigError,
        workflowConfigModalOpen,
        setWorkflowConfigModalOpen,
        connectionStatus,
        start,
        stop,
        isStarting,
        feedbackMessages,
        getAudioInputDevices,
        localStream,
        micSendWarning,
    } = useWebSocketRTC({
        workflowId,
        workflowRunId,
        accessToken,
        initialContextVariables,
        onNodeTransition,
    });
    const [micReady, setMicReady] = useState(false);
    const [micPermissionError, setMicPermissionError] = useState<string | null>(null);
    const [previewStream, setPreviewStream] = useState<MediaStream | null>(null);
    const autoStartedRef = useRef(false);

    const labeledMicInputs = audioInputs.filter(
        (device) => device.label && device.deviceId && device.deviceId !== "default"
    );

    useEffect(() => {
        let cancelled = false;
        let stream: MediaStream | null = null;

        const prepareMicrophone = async () => {
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                if (cancelled) {
                    stream.getTracks().forEach((track) => track.stop());
                    return;
                }
                setPreviewStream(stream);
                await getAudioInputDevices();
                setMicReady(true);
            } catch {
                if (!cancelled) {
                    setMicPermissionError(
                        "Microphone access is required. Allow mic access in your browser, then click Retry."
                    );
                }
            }
        };

        void prepareMicrophone();

        return () => {
            cancelled = true;
            if (stream) {
                stream.getTracks().forEach((track) => track.stop());
            }
            setPreviewStream(null);
        };
    }, [getAudioInputDevices]);

    useEffect(() => {
        autoStartedRef.current = false;
    }, [workflowRunId]);

    useEffect(() => {
        if (!micReady || autoStartedRef.current || connectionActive || isCompleted) {
            return;
        }
        autoStartedRef.current = true;

        const startCall = async () => {
            if (previewStream) {
                previewStream.getTracks().forEach((track) => track.stop());
                setPreviewStream(null);
            }
            await start();
        };

        void startCall();
    }, [micReady, start, previewStream, connectionActive, isCompleted, workflowRunId]);

    const activeMicStream = localStream ?? previewStream;
    const canManualStart =
        micReady &&
        !connectionActive &&
        !isStarting &&
        !isCompleted &&
        connectionStatus === "failed";

    const endButtonLabel = connectionActive
        ? "End Call"
        : isCompleted
            ? "Start Another Test"
            : connectionStatus === "failed"
                ? "Retry Call"
                : "Starting Test...";

    const beginCall = async () => {
        if (previewStream) {
            previewStream.getTracks().forEach((track) => track.stop());
            setPreviewStream(null);
        }
        autoStartedRef.current = true;
        await start();
    };

    const handleFooterAction = async () => {
        if (connectionActive) {
            stop();
            return;
        }
        if (isCompleted || connectionStatus === "failed") {
            await onRequestNewRun();
            return;
        }
        if (canManualStart) {
            await beginCall();
        }
    };

    return (
        <>
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border/70 bg-background">
                <div className="min-h-0 flex-1 overflow-hidden bg-muted/15">
                    <RealtimeFeedback
                        mode="live"
                        messages={feedbackMessages}
                        isCallActive={connectionActive}
                        isCallCompleted={isCompleted}
                    />
                </div>

                <div className="border-t border-border/70 bg-background px-4 py-3">
                    <div className="flex flex-col gap-3">
                        {micPermissionError ? (
                            <p className="text-center text-sm text-destructive">{micPermissionError}</p>
                        ) : null}
                        {!connectionActive && labeledMicInputs.length > 1 ? (
                            <div className="space-y-2">
                                <Label htmlFor="test-mic-input" className="text-xs text-muted-foreground">
                                    Microphone
                                </Label>
                                <Select
                                    value={selectedAudioInput || labeledMicInputs[0]?.deviceId}
                                    onValueChange={setSelectedAudioInput}
                                    disabled={connectionActive || isStarting}
                                >
                                    <SelectTrigger id="test-mic-input" className="h-9">
                                        <SelectValue placeholder="Select microphone" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {labeledMicInputs.map((device) => (
                                            <SelectItem key={device.deviceId} value={device.deviceId}>
                                                {device.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        ) : !micReady && !micPermissionError ? (
                            <p className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                                <Mic className="h-4 w-4" />
                                Waiting for microphone access...
                            </p>
                        ) : null}
                        {activeMicStream ? (
                            <MicLevelIndicator stream={activeMicStream} />
                        ) : null}
                        <ConnectionStatus connectionStatus={connectionStatus} />
                        {permissionError ? (
                            <p className="text-center text-sm text-destructive">{permissionError}</p>
                        ) : null}
                        {micSendWarning ? (
                            <p className="text-center text-sm text-amber-600 dark:text-amber-400">
                                {micSendWarning}
                            </p>
                        ) : null}
                        <Button
                            onClick={handleFooterAction}
                            disabled={
                                (isStarting && connectionStatus !== "failed") ||
                                (!connectionActive &&
                                    !isCompleted &&
                                    connectionStatus !== "failed" &&
                                    !canManualStart)
                            }
                            variant={connectionActive ? "destructive" : "default"}
                            className="w-full"
                        >
                            {isStarting && connectionStatus !== "failed" ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Starting Test...
                                </>
                            ) : connectionActive ? (
                                <>
                                    <Phone className="h-4 w-4" />
                                    {endButtonLabel}
                                </>
                            ) : connectionStatus === "failed" || isCompleted ? (
                                <>
                                    <RefreshCw className="h-4 w-4" />
                                    {endButtonLabel}
                                </>
                            ) : (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    {endButtonLabel}
                                </>
                            )}
                        </Button>
                    </div>
                </div>

                <audio ref={audioRef} autoPlay playsInline className="hidden" />
            </div>

            <ApiKeyErrorDialog
                open={apiKeyModalOpen}
                onOpenChange={setApiKeyModalOpen}
                error={apiKeyError}
                errorCode={apiKeyErrorCode}
                onNavigateToBilling={() => router.push("/billing")}
                onNavigateToDevelopers={() => router.push("/api-keys")}
                onNavigateToModelConfig={() => router.push("/model-configurations")}
            />

            <WorkflowConfigErrorDialog
                open={workflowConfigModalOpen}
                onOpenChange={setWorkflowConfigModalOpen}
                error={workflowConfigError}
                onNavigateToWorkflow={() => router.push(`/workflow/${workflowId}`)}
            />
        </>
    );
}
