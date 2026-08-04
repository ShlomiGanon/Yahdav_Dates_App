import { Response } from 'express';
import { ValidationError } from 'express-validator';

// Every response — success or failure — is sent as HTTP 200. The body's
// `success` boolean and `message` string are the only signal the frontend
// needs; `error` is a stable machine-readable code (used by the frontend's
// auth interceptor to detect "unauthorized" specifically) and `errors`
// carries express-validator's full per-field detail when relevant.

const ERROR_MESSAGES: Record<string, string> = {
  unauthorized: 'יש להתחבר מחדש',
  forbidden: 'אין לך הרשאה לבצע פעולה זו',
  not_found: 'הפריט המבוקש לא נמצא',
  invalid_credentials: 'שם משתמש או סיסמה שגויים',
  username_taken: 'שם המשתמש כבר תפוס',
  email_taken: 'האימייל כבר קיים במערכת',
  missing_file: 'יש לבחור קובץ',
  invalid_file_type: 'סוג הקובץ אינו נתמך',
  file_too_large: 'הקובץ גדול מדי (מקסימום 8MB)',
  photo_limit_reached: 'ניתן להעלות עד 4 תמונות נוספות',
  cannot_block_self: 'לא ניתן לחסום את עצמך',
  cannot_change_own_status: 'לא ניתן לשנות את הסטטוס של המשתמש שלך',
  cannot_delete_self: 'לא ניתן למחוק את המשתמש שלך',
  blocked: 'לא ניתן לשלוח הודעה למשתמש זה',
  session_not_found: 'ההתחברות פגה, יש להתחבר מחדש',
  session_expired: 'ההתחברות פגה, יש להתחבר מחדש',
  invalid_token: 'ההתחברות פגה, יש להתחבר מחדש',
  missing_refresh_token: 'חסר טוקן רענון',
  validation_error: 'הנתונים שהוזנו אינם תקינים',
  internal_error: 'אירעה שגיאה, נסה שוב מאוחר יותר',
};

export function errorMessage(code: string): string
{
  return ERROR_MESSAGES[code] ?? 'אירעה שגיאה, נסה שוב מאוחר יותר';
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
