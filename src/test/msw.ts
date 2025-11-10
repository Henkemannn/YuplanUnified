import { setupServer } from 'msw/node';
import { http } from 'msw';

export const server = setupServer();
export { http } from 'msw';
