# @unclone/kyc-node

The official Node.js and TypeScript client library for the Unclone Identity Verification Service.

## Installation

```bash
npm install @unclone/kyc-node
```

## Usage

### 1. Initialize Client
```typescript
import { UncloneKycClient } from '@unclone/kyc-node';

const client = new UncloneKycClient({
  apiKey: process.env.KYC_API_KEY!,
  baseUrl: process.env.KYC_BASE_URL || 'https://api.unclone.ai',
});
```

### 2. Create Verification Session
```typescript
const session = await client.createVerification({
  referenceId: 'user_12345',
  expected: {
    name: 'Sarah Connor',
    dob: '1984-02-28',
    idLast4: '9842',
  },
  policy: 'strict',
  idempotencyKey: 'idemp_user_12345',
});

// Pass session.flow_url to your mobile app or frontend WebView
console.log('Session ID:', session.id);
console.log('Flow URL:', session.flow_url);
```

### 3. Retrieve Verification Status
```typescript
const result = await client.getVerification(session.id);
console.log('Status:', result.status);               // 'completed'
console.log('Decision:', result.decision);           // 'approved' | 'needs_review' | 'rejected_recommended'
console.log('Final Decision:', result.final_decision);
console.log('Trust score:', result.trust);
console.log('Reasons:', result.reasons);
```

### 4. Human Review Override
```typescript
const reviewed = await client.reviewVerification(session.id, {
  decision: 'approved',
  note: 'Physically inspected national ID in branch office',
});
console.log('New decision:', reviewed.final_decision);
```

### 5. Verify Incoming Webhooks (Express, Fastify, Next.js)
```typescript
import { verifyWebhook, WebhookVerificationError } from '@unclone/kyc-node';

app.post('/webhooks/kyc', express.raw({ type: 'application/json' }), (req, res) => {
  const signature = req.headers['x-kyc-signature'] as string;
  try {
    const event = verifyWebhook(
      req.body,
      signature,
      process.env.KYC_WEBHOOK_SECRET!,
      300 // 5 minute replay tolerance
    );
    console.log('Verified KYC Event:', event.type, event.data.id);
    res.json({ received: true });
  } catch (err) {
    if (err instanceof WebhookVerificationError) {
      return res.status(400).send('Invalid webhook signature');
    }
    return res.status(500).send('Internal Error');
  }
});
```
