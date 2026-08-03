let _token: string | null = null;

export const tokenStore = {
  get: () => _token,
  set: (t: string | null) => { _token = t; },
};
