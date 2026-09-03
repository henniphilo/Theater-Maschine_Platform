import Link from "next/link";

import { LightInventoryPanel } from "@/components/settings/LightInventoryPanel";
import { MediaCueAdminPanel } from "@/components/settings/MediaCueAdminPanel";
import { RuntimeSettingsPanel } from "@/components/settings/RuntimeSettingsPanel";
import { VenueProfilePanel } from "@/components/settings/VenueProfilePanel";

export default function EinstellungenPage() {
  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Betriebs-Einstellungen</h1>
      </div>
      <p className="textMuted">
        Laufzeit-Overrides für Dramaturgie, Ausgaben und Teil-2-Prepare — getrennt vom Technik-Test.{" "}
        <Link href="/technik">Zur Technik →</Link>
      </p>
      <VenueProfilePanel />
      <RuntimeSettingsPanel />
      <LightInventoryPanel />
      <MediaCueAdminPanel />
    </main>
  );
}
