import { useCallback, useEffect, useState } from "react";

export const useDeviceInputs = () => {
    const [audioInputs, setAudioInputs] = useState<MediaDeviceInfo[]>([]);
    const [selectedAudioInput, setSelectedAudioInput] = useState('');
    const [permissionError, setPermissionError] = useState<string | null>(null);

    const getAudioInputDevices = useCallback(async () => {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioDevices = devices.filter(device => device.kind === 'audioinput');
            setAudioInputs(audioDevices);

            const labeledDevice = audioDevices.find(
                (device) =>
                    device.label &&
                    device.deviceId &&
                    device.deviceId !== 'default' &&
                    device.deviceId !== 'communications'
            );
            if (labeledDevice) {
                setSelectedAudioInput(labeledDevice.deviceId);
            }
        } catch {
            setPermissionError('Could not enumerate devices');
        }
    }, []);

    useEffect(() => {
        getAudioInputDevices();
    }, [getAudioInputDevices]);

    return {
        audioInputs,
        selectedAudioInput,
        setSelectedAudioInput,
        permissionError,
        setPermissionError,
        getAudioInputDevices
    };
};
