import { Request, Response, NextFunction } from 'express';
import { SessionModel, AccessPayload } from '../models/SessionModel';
import { fail } from '../utils/responses';

export interface AuthRequest extends Request {
  user: AccessPayload;
}

export function authenticate(req: Request, res: Response, next: NextFunction): void {
  const auth = req.headers.authorization;
  if (!auth?.startsWith('Bearer ')) {
    fail(res, 'unauthorized');
    return;
  }

  try {
    const payload = SessionModel.verifyAccess(auth.slice(7));
    (req as AuthRequest).user = payload;
    next();
  } catch {
    fail(res, 'unauthorized');
  }
}

export function requireAdmin(req: Request, res: Response, next: NextFunction): void {
  const user = (req as AuthRequest).user;
  if (!user?.is_admin) {
    fail(res, 'forbidden');
    return;
  }
  next();
}
