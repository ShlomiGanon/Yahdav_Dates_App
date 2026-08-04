import { Response } from 'express';
import { ValidationError } from 'express-validator';
import { serverMessage } from '@yahdav/shared/copy/server';

// Every response — success or failure — is sent as HTTP 200. The body's
// `success` boolean and `message` string are the only signal the frontend
// needs; `error` is a stable machine-readable code (used by the frontend's
// auth interceptor to detect "unauthorized" specifically) and `errors`
// carries express-validator's full per-field detail when relevant.
//
// Hebrew message text lives in @shared/copy/server, not here — this is
// just the thinnest possible wrapper so every fail() call site keeps
// working unchanged.

export function errorMessage(code: string): string
{
  return serverMessage(code);
}

export function ok(res: Response, data: object = {}, message = 'הפעולה בוצעה בהצלחה'): void
{
  res.status(200).json({ success: true, message, ...data });
}

export function fail(res: Response, error: string, extra: Record<string, unknown> = {}): void
{
  res.status(200).json({ success: false, error, message: errorMessage(error), ...extra });
}

export function failValidation(res: Response, errors: ValidationError[]): void
{
  const first = errors[0] as { msg?: unknown } | undefined;
  const message = first && typeof first.msg === 'string' ? first.msg : errorMessage('validation_error');
  res.status(200).json({ success: false, error: 'validation_error', message, errors });
}
