import { Download, X } from "lucide-react";

export type AddToLabModalProps = {
  onCancel: () => void;
};

const DESKTOP_DOWNLOAD_URL = "https://biosimulant.dev/download";

export function AddToLabModal({ onCancel }: AddToLabModalProps) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <form
        className="modal add-to-lab-modal"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="modal-header">
          <h2>Add to lab</h2>
          <button type="button" className="icon-button small" onClick={onCancel} title="Close">
            <X size={14} />
          </button>
        </div>
        <div className="modal-body">
          <div className="add-to-lab-signin">
            <p>
              <strong>Adding models and child labs is available in the desktop app.</strong>
            </p>
            <p className="muted small">
              The web UI you are using runs locally via <code>biosimulant labs serve</code> and supports editing and
              running an existing lab. To browse the Hub, import packages, or add new components to this lab, install
              the Biosimulant Desktop app.
            </p>
            <p>
              <a href={DESKTOP_DOWNLOAD_URL} target="_blank" rel="noreferrer">
                <Download size={12} aria-hidden /> Get the Biosimulant Desktop app →
              </a>
            </p>
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="button" onClick={onCancel}>
            Close
          </button>
        </div>
      </form>
    </div>
  );
}
