/** Auth store: holds the current user (or null), refreshed on demand. */
import { writable, get } from 'svelte/store';
import { api, ApiError, type UserOut } from './api';

const _user = writable<UserOut | null | undefined>(undefined);   // undefined = unknown
export const user = { subscribe: _user.subscribe };

export async function refreshUser(): Promise<UserOut | null> {
  try {
    const me = await api.me();
    _user.set(me);
    return me;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      _user.set(null);
      return null;
    }
    throw e;
  }
}

export async function logout(): Promise<void> {
  await api.logout();
  _user.set(null);
}

export function currentUser(): UserOut | null | undefined {
  return get(_user);
}
