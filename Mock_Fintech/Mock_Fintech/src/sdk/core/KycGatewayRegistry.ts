import { IKycSdkGateway } from './IKycSdkGateway';
import { MockCustomKycSdkGateway } from '../mock/MockCustomKycSdkGateway';
import { UnCloneKycSdkAdapter } from '../adapters/UnCloneKycSdkAdapter';

/**
 * KycGatewayRegistry
 * 
 * Central registry managing available KYC SDK implementations.
 * Enables plug-and-play swapping between different vendor SDKs or custom proprietary modules.
 */
class KycGatewayRegistryImpl {
  private gateways: Map<string, IKycSdkGateway> = new Map();
  private activeGatewayId: string | null = null;

  constructor() {
    // Register UnClone AI Identity SDK as the primary gateway
    const unCloneGateway = new UnCloneKycSdkAdapter();
    const mockGateway = new MockCustomKycSdkGateway();

    this.registerGateway(unCloneGateway);
    this.registerGateway(mockGateway);
    this.setActiveGateway(unCloneGateway.id);
  }

  /**
   * Registers a new custom KYC SDK gateway.
   * 
   * Example:
   * ```ts
   * KycGatewayRegistry.registerGateway(new MyCompanyCustomKycGateway());
   * ```
   */
  public registerGateway(gateway: IKycSdkGateway): void {
    this.gateways.set(gateway.id, gateway);
    if (!this.activeGatewayId) {
      this.activeGatewayId = gateway.id;
    }
  }

  /**
   * Sets the currently active gateway used by the app.
   */
  public setActiveGateway(gatewayId: string): void {
    if (!this.gateways.has(gatewayId)) {
      throw new Error(`Gateway with id '${gatewayId}' is not registered.`);
    }
    this.activeGatewayId = gatewayId;
  }

  /**
   * Retrieves the currently active gateway.
   */
  public getActiveGateway(): IKycSdkGateway {
    if (!this.activeGatewayId || !this.gateways.has(this.activeGatewayId)) {
      throw new Error('No active KYC SDK gateway registered.');
    }
    return this.gateways.get(this.activeGatewayId)!;
  }

  /**
   * Retrieves a specific gateway by its ID.
   */
  public getGateway(id: string): IKycSdkGateway | undefined {
    return this.gateways.get(id);
  }

  /**
   * Lists all registered KYC SDK gateways.
   */
  public listGateways(): Array<{ id: string; name: string; version: string }> {
    return Array.from(this.gateways.values()).map((g) => ({
      id: g.id,
      name: g.name,
      version: g.version,
    }));
  }
}

export const KycGatewayRegistry = new KycGatewayRegistryImpl();
