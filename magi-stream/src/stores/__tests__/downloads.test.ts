import { describe, expect, it } from "vitest";
import { requiredDownloadAds } from "../downloads";
describe("pubs avant téléchargement", () => {
  it("1 pub pour un seul épisode", () => expect(requiredDownloadAds(1)).toBe(1));
  it("3 pubs pour une sélection", () => expect(requiredDownloadAds(4)).toBe(3));
});
