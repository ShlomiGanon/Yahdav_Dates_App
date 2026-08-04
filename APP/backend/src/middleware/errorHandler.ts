import { Request, Response, NextFunction } from 'express';
import { fail } from '../utils/responses';

export function errorHandler(
  err: Error,
  _req: Request,
  res: Response,
  _next: NextFunction,
): void {
  console.error('[error]', err.message);
  fail(res, 'internal_error');
}
