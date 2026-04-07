import { authHandlers } from './auth';
import { healthHandlers } from './health';
import { marketplaceHandlers } from './marketplace';
import { negotiationHandlers } from './negotiation';
import { escrowHandlers } from './escrow';
import { enterpriseHandlers } from './enterprise';
import { apikeysHandlers } from './apikeys';
import { sellerProfileHandlers } from './sellerProfile';
import { sseHandlers } from './sse';
import { complianceHandlers } from './compliance';
import { adminHandlers } from './admin';
import { treasuryHandlers } from './treasury';
import { walletHandlers } from './wallet';

export const handlers = [
  ...authHandlers,
  ...healthHandlers,
  ...marketplaceHandlers,
  ...negotiationHandlers,
  ...escrowHandlers,
  ...enterpriseHandlers,
  ...apikeysHandlers,
  ...sellerProfileHandlers,
  ...sseHandlers,
  ...complianceHandlers,
  ...adminHandlers,
  ...treasuryHandlers,
  ...walletHandlers,
];
