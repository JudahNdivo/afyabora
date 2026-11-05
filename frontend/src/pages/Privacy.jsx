import LegalPage from "../components/LegalPage";
import { SUPPORT_EMAIL } from "../config";

export default function Privacy() {
  return (
    <LegalPage title="Privacy policy" updated="5 November 2026">
      <p>
        AfyaBora is a student project built which gives general information about sexually transmitted infections in English and
        Kiswahili. This page explains what we keep about you and why. We aim to
        handle your data in line with Kenya's Data Protection Act, 2019.
      </p>

      <h2>What we keep</h2>
      <ul>
        <li>Your email address and the username you choose.</li>
        <li>
          Your password. It is stored in scrambled (hashed) form by our login
          provider, so nobody at AfyaBora can read it. If you use Google to sign
          in, we receive your name and email from Google, not your Google password.
        </li>
        <li>
          If you turn on the authenticator app, the login provider stores the
          secret needed to check your codes.
        </li>
        <li>
          Your conversations: the questions you ask and the answers you get are kept
          so you can open them again later.
        </li>
        <li>
          Simple usage statistics, such as the language, the topic and how long an
          answer took. These are not linked to your account.
        </li>
        <li>
          Technical logs kept by our hosting provider, such as your IP address
          when you use the site.
        </li>
      </ul>

      <h2>Who can see your conversations</h2>
      <p>
        You can. Administrators only see totals on the dashboard, for example how
        many questions were asked in each language. They cannot read your
        conversations through the app. The developer can technically reach the
        database for maintenance, and does not read conversations for any other
        purpose.
      </p>

      <h2>Other services that handle your data</h2>
      <ul>
        <li>
          Supabase stores the database and handles login. Its servers are in the
          United States (North Virginia).
        </li>
        <li>Render runs the website. Its servers are also in the United States.</li>
        <li>
          Google's Gemini service writes the answers. Your question and a few of
          your recent messages in the same conversation are sent to Google for
          this. Please do not type your full name, phone number, ID number or
          other details that identify you into a question.
        </li>
        <li>Gmail is used to send sign-up and password reset emails.</li>
      </ul>

      <h2>Your choices</h2>
      <ul>
        <li>You can delete any conversation from the chat screen.</li>
        <li>
          You can change your username, or delete your account and all your
          conversations from your profile page. This cannot be undone.
        </li>
        <li>
          Conversations are kept until you delete them.
        </li>
      </ul>

      <h2>Age</h2>
      <p>AfyaBora is meant for people aged 18 and over.</p>

      <h2>Questions</h2>
      <p>
        Write to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> for any
        question about your data or to ask for something to be removed.
      </p>
    </LegalPage>
  );
}