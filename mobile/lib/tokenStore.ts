import * as SecureStore from "expo-secure-store";
import type { TokenStorage } from "@douini/shared";

const ACCESS_KEY = "douini_access";
const REFRESH_KEY = "douini_refresh";

export const tokenStore: TokenStorage = {
  getAccessToken() {
    return SecureStore.getItem(ACCESS_KEY);
  },
  getRefreshToken() {
    return SecureStore.getItem(REFRESH_KEY);
  },
  setTokens(access: string, refresh: string) {
    SecureStore.setItem(ACCESS_KEY, access);
    SecureStore.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    SecureStore.deleteItemAsync(ACCESS_KEY);
    SecureStore.deleteItemAsync(REFRESH_KEY);
  },
};
