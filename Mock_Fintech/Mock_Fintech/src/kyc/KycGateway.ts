export interface KycSessionResult { sessionId: string; flowUrl: string; }
export interface KycUserInfo { referenceId: string; name?: string; dob?: string; idLast4?: string; policy?: string; }
export interface IKycSdkGateway { readonly name: string; createSession(user: KycUserInfo): Promise<KycSessionResult>; }
const _reg = new Map<string, IKycSdkGateway>();
export const KycGatewayRegistry = {
  register(g: IKycSdkGateway) { _reg.set(g.name, g); },
  get(n: string) { return _reg.get(n); },
  default(): IKycSdkGateway { const f = _reg.values().next().value; if (!f) throw new Error('No KYC gateway'); return f; },
};
// For Android emulator use 10.0.2.2. For physical device on WiFi use laptop LAN IP e.g. http://192.168.1.100:8000
const KYC_API_BASE = 'http://10.0.2.2:8000';
const KYC_API_KEY  = 'kyc_demo_strict_key';
export class UnCloneKycGateway implements IKycSdkGateway {
  readonly name = 'UnClone KYC';
  async createSession(user: KycUserInfo): Promise<KycSessionResult> {
    const resp = await fetch(KYC_API_BASE + '/v1/verifications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + KYC_API_KEY },
      body: JSON.stringify({ reference_id: user.referenceId, policy: user.policy || 'strict',
        expected: { name: user.name, dob: user.dob, id_last4: user.idLast4 } }),
    });
    if (!resp.ok) { const t = await resp.text().catch(()=>''); throw new Error('KYC ' + resp.status + ': ' + t.slice(0,120)); }
    const data = await resp.json();
    return { sessionId: data.id, flowUrl: data.flow_url };
  }
}
KycGatewayRegistry.register(new UnCloneKycGateway());
