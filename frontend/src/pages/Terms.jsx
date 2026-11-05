import LegalPage from "../components/LegalPage";
import { SUPPORT_EMAIL } from "../config";

export default function Terms() {
  return (
    <LegalPage title="Terms of use" updated="5 November 2026">
      <p>
        By creating an account or using AfyaBora you agree to these terms. They are
        short on purpose.
      </p>

      <h2>This is health education, not medical care</h2>
      <p>
        AfyaBora gives general information about sexually transmitted infections.
        It does not diagnose, treat or replace a doctor, nurse or clinic. Answers
        are written by an AI system from a collection of health education
        material. They can be wrong, out of date or incomplete and Kiswahili
        answers may contain mistakes. Do not use AfyaBora to decide on a
        medicine, a dose or whether to seek care. If you think you have an
        infection, or you are worried, please visit a health facility.
      </p>
      <p>
        In an emergency, call 999 or 112, or go to the nearest hospital straight
        away.
      </p>

      <h2>A student project</h2>
      <p>
        AfyaBora is a prototype built for a university project. It may be slow,
        change, or go offline at any time and it comes with no guarantee.
      </p>

      <h2>Using it fairly</h2>
      <ul>
        <li>Keep your password private and use your own email address.</li>
        <li>
          Do not try to break the service, reach other people's accounts or data,
          or send automated or abusive traffic.
        </li>
        <li>Do not use it to harass anyone.</li>
      </ul>

      <h2>Liability</h2>
      <p>
        AfyaBora is provided as it is. To the extent the law allows, its creator
        is not responsible for harm that comes from relying on its answers.
      </p>

      <h2>Your data</h2>
      <p>The privacy policy explains what we keep and why.</p>

      <h2>Changes and contact</h2>
      <p>
        We may update these terms and the date at the top will change when we do.
        Questions can go to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
      </p>
    </LegalPage>
  );
}