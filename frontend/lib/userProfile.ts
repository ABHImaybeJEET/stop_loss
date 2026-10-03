import { doc, getDoc, setDoc } from "firebase/firestore";
import { auth, db } from "@/lib/firebase";

export interface UserProfile {
  fullName: string;
  role: string;
  organization: string;
  location: string;
  updatedAt?: string;
}

const CACHE_PREFIX = "stoploss_profile_";

function cacheKey(id: string): string {
  return `${CACHE_PREFIX}${id}`;
}

function readCache(id: string): Partial<UserProfile> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(cacheKey(id));
    return raw ? (JSON.parse(raw) as Partial<UserProfile>) : null;
  } catch {
    return null;
  }
}

function writeCache(id: string, profile: UserProfile): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(cacheKey(id), JSON.stringify(profile));
  } catch {
    // Storage may be full or blocked; Firestore remains the source of truth.
  }
}

const EMPTY_PROFILE: UserProfile = { fullName: "", role: "", organization: "", location: "" };

/** Returns the stored profile (Firestore first, then local cache); empty fields when none exists. */
export async function fetchUserProfile(id: string | null | undefined): Promise<UserProfile> {
  if (!id) return { ...EMPTY_PROFILE };
  const cached = readCache(id);
  try {
    const snap = await getDoc(doc(db, "users", id));
    if (snap.exists()) {
      const remote = snap.data() as Partial<UserProfile>;
      const profile = { ...EMPTY_PROFILE, ...remote };
      if (profile.fullName) writeCache(id, profile);
      return profile;
    }
  } catch (err) {
    console.warn("Profile fetch from Firestore failed; using local cache.", err);
  }
  return { ...EMPTY_PROFILE, ...cached };
}

export async function saveUserProfile(profile: UserProfile, id: string | null | undefined): Promise<void> {
  if (!id) return;
  writeCache(id, profile);
  // The email/password login path checks onboarding by email, so mirror the cache under it.
  const email = auth.currentUser?.email;
  if (email && email !== id) writeCache(email, profile);
  try {
    await setDoc(doc(db, "users", id), profile, { merge: true });
  } catch (err) {
    console.warn("Profile save to Firestore failed; kept in local cache.", err);
  }
}

export function hasCompletedOnboarding(id: string | null | undefined): boolean {
  if (!id) return false;
  return Boolean(readCache(id)?.fullName);
}
