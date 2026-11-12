import { useCallback, useState } from "react";
import { changeSetting, fetchModels, fetchSettings } from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { LoadError } from "../components/LoadError";
import { PageHeader } from "../components/PageHeader";
import { formatTime } from "../time";
import { APPEARANCES, savedAppearance, setAppearance } from "../theme";
import type { Appearance } from "../theme";
import type { AllowedModel, Setting } from "../types";
import { useMe } from "../useMe";
import { usePolling } from "../usePolling";

function AppearanceChoice() {
  const [appearance, setChoice] = useState<Appearance>(savedAppearance);

  return (
    <fieldset>
      <legend>Appearance</legend>
      {APPEARANCES.map(({ value, label }) => (
        <label key={value}>
          <input
            type="radio"
            name="appearance"
            checked={appearance === value}
            onChange={() => {
              setChoice(value);
              setAppearance(value);
            }}
          />{" "}
          {label}
        </label>
      ))}
      <p>This browser remembers your choice.</p>
    </fieldset>
  );
}

function SettingRow({
  setting,
  canChange,
  onAsk,
}: Readonly<{
  setting: Setting;
  canChange: boolean;
  onAsk: (setting: Setting, value: string) => void;
}>) {
  const [value, setValue] = useState(setting.value);

  return (
    <tr>
      <th scope="row">{setting.label}</th>
      <td className="number">
        {canChange ? (
          <input
            aria-label={`${setting.group}: ${setting.label}`}
            className="number"
            inputMode="decimal"
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
            }}
          />
        ) : (
          setting.value
        )}
      </td>
      <td>{setting.unit}</td>
      <td>
        {setting.changed_by !== null && setting.changed_on !== null
          ? `${setting.changed_by}, ${formatTime(setting.changed_on)}`
          : "Not changed since the start"}
      </td>
      {canChange && (
        <td>
          <button
            type="button"
            disabled={value === setting.value}
            onClick={() => {
              onAsk(setting, value);
            }}
          >
            Save
          </button>
        </td>
      )}
    </tr>
  );
}

function SettingsGroup({
  group,
  settings,
  canChange,
  onAsk,
}: Readonly<{
  group: string;
  settings: Setting[];
  canChange: boolean;
  onAsk: (setting: Setting, value: string) => void;
}>) {
  return (
    <section>
      <h2>{group}</h2>
      <DataTable>
        <thead>
          <tr>
            <th>Setting</th>
            <th className="number">Value</th>
            <th>Unit</th>
            <th>Last changed by</th>
            {canChange && <th />}
          </tr>
        </thead>
        <tbody>
          {settings.map((setting) => (
            <SettingRow
              key={`${setting.key}-${setting.value}`}
              setting={setting}
              canChange={canChange}
              onAsk={onAsk}
            />
          ))}
        </tbody>
      </DataTable>
    </section>
  );
}

function ModelsTable({ models }: Readonly<{ models: AllowedModel[] }>) {
  return (
    <section>
      <h2>Models allowed</h2>
      <p>
        The claim agent may use these models. They are set in a file and can't
        be changed here.
      </p>
      <DataTable>
        <thead>
          <tr>
            <th>Model</th>
            <th>Reasoning efforts</th>
            <th className="number">Input ($ per million tokens)</th>
            <th className="number">Output ($ per million tokens)</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr key={model.model}>
              <th scope="row" className="mono">
                {model.model}
              </th>
              <td>{model.reasoning_efforts.join(", ")}</td>
              <td className="number mono">
                {model.input_price_per_million.toFixed(2)}
              </td>
              <td className="number mono">
                {model.output_price_per_million.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </section>
  );
}

export function SettingsPage() {
  const me = useMe();
  const [settings, setSettings] = useState<Setting[]>([]);
  const [models, setModels] = useState<AllowedModel[]>([]);
  const [asked, setAsked] = useState<{
    setting: Setting;
    value: string;
  } | null>(null);
  const [message, setMessage] = useState("");
  const canChange = me?.can_approve_over_limit === true;

  const load = useCallback(
    () =>
      Promise.all([fetchSettings(), fetchModels()]).then(([s, m]) => {
        setSettings(s);
        setModels(m);
      }),
    [],
  );
  const failed = usePolling(load, false);

  const confirm = () => {
    if (asked === null) return;
    setMessage("");
    changeSetting(asked.setting.key, asked.value)
      .then(load)
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Could not save.");
      });
    setAsked(null);
  };

  const groups = [...new Set(settings.map((setting) => setting.group))];

  return (
    <main className="panel">
      <PageHeader title="Settings">
        What the platform works to: the approval limit, the business objectives
        for improving the agent, and how a round is paid for.
      </PageHeader>
      {failed && <LoadError />}
      {message && <p role="alert">{message}</p>}
      {!canChange && (
        <p>
          {me?.name ?? "You"} can't change settings: only a handler who can sign
          off payouts over the limit can.
        </p>
      )}
      <AppearanceChoice />
      {groups.map((group) => (
        <SettingsGroup
          key={group}
          group={group}
          settings={settings.filter((setting) => setting.group === group)}
          canChange={canChange}
          onAsk={(setting, value) => {
            setAsked({ setting, value });
          }}
        />
      ))}
      <ModelsTable models={models} />
      {asked && (
        <ConfirmDialog
          title={`Change ${asked.setting.label.toLowerCase()}?`}
          confirmLabel="Change it"
          onConfirm={confirm}
          onCancel={() => {
            setAsked(null);
          }}
        >
          <p>
            {asked.setting.group}: {asked.setting.label} changes from{" "}
            {asked.setting.value} to {asked.value} ({asked.setting.unit}). The
            change is recorded with your name and the time.
          </p>
        </ConfirmDialog>
      )}
    </main>
  );
}
