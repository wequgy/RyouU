import React from 'react';
import { KycResult, KycStartParams, UncloneKycConfig } from './types';
export interface UncloneKycModalProps {
    visible: boolean;
    config: UncloneKycConfig;
    params: KycStartParams;
    onComplete: (result: KycResult) => void;
    onCancel: () => void;
    onError?: (error: Error) => void;
}
export declare const UncloneKycModal: React.FC<UncloneKycModalProps>;
