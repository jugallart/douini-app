import { useState } from "react";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

export function DeletePlanDialog({ garminConnected, onClose, onConfirm, deleting }: {
  garminConnected: boolean;
  onClose: () => void;
  onConfirm: (withGarmin: boolean) => void;
  deleting?: boolean;
}) {
  const [withGarmin, setWithGarmin] = useState(garminConnected);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <Card className="w-full max-w-md">
        <div onClick={(e) => e.stopPropagation()}>
          <h3 className="mb-2 text-lg font-semibold">Supprimer le plan ?</h3>
          <p className="text-sm text-gray-600">Le plan et ses séances seront supprimés. Cette action est irréversible.</p>
          {garminConnected && (
            <label className="mt-4 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={withGarmin} onChange={(e) => setWithGarmin(e.target.checked)} />
              Supprimer aussi les séances Garmin
            </label>
          )}
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>Annuler</Button>
            <Button variant="danger" onClick={() => onConfirm(withGarmin)} loading={deleting}>Supprimer</Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
