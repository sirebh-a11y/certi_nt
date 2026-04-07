const emailPattern = /^[^@\s]+@(?:localhost|(?:[^.@\s]+\.)+[^.@\s]+)$/i;

export const EMAIL_ERROR_MESSAGE = "Inserisci un'email valida, ad esempio nome@azienda.it";

export function isValidEmail(value) {
  return emailPattern.test(String(value).trim());
}
