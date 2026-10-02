/**
 * Demo rule: treat as admin when the local part of the email contains `+admin`
 * (e.g. `you+admin@gmail.com`). Replace with JWT role from FastAPI in production.
 */
export function isAdminEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  const [local] = email.toLowerCase().split('@');
  return local.includes('+admin');
}
