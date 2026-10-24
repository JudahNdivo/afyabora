// where people write when they cannot use their authenticator app;
// change it here and every page picks it up
export const SUPPORT_EMAIL = "judah.ndivo@strathmore.edu";
export const SUPPORT_SUBJECT = "AfyaBora: lost access to my authenticator";

// opens a new message in Gmail in the browser, with the address and
// subject already filled in
export const SUPPORT_LINK =
  "https://mail.google.com/mail/?view=cm&fs=1" +
  `&to=${encodeURIComponent(SUPPORT_EMAIL)}` +
  `&su=${encodeURIComponent(SUPPORT_SUBJECT)}`;