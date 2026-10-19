declare module 'react-native-webview' {
  import * as React from 'react';
  import { ViewProps } from 'react-native';

  export interface WebViewMessageEvent {
    nativeEvent: {
      data: string;
      [key: string]: any;
    };
  }

  export interface WebViewProps extends ViewProps {
    source?: { uri?: string; html?: string; [key: string]: any };
    onMessage?: (event: WebViewMessageEvent) => void;
    allowsInlineMediaPlayback?: boolean;
    mediaPlaybackRequiresUserAction?: boolean;
    javaScriptEnabled?: boolean;
    domStorageEnabled?: boolean;
    [key: string]: any;
  }

  export class WebView extends React.Component<WebViewProps> {}
}

declare module 'expo-screen-capture' {
  export function preventScreenCaptureAsync(key?: string): Promise<void>;
  export function allowScreenCaptureAsync(key?: string): Promise<void>;
}
