import type { MediPilotApi } from './types';
import { createMockAdapter } from './adapters/mock';
import { createLiveAdapter } from './adapters/live';

const SOURCE = process.env.NEXT_PUBLIC_MP_SOURCE ?? 'mock';

function createApi(): MediPilotApi {
  if (SOURCE === 'live') {
    return createLiveAdapter();
  }
  return createMockAdapter();
}

export const api: MediPilotApi = createApi();
