export class ConcurrencyError extends Error {
  code = 412 as const;
  current_etag: string | null;
  detail?: string;
  constructor(message: string = "Precondition Failed", current_etag: string | null = null, detail?: string) {
    super(message);
    this.name = "ConcurrencyError";
    this.current_etag = current_etag;
    this.detail = detail;
  }
}

export class AuthzError extends Error {
  code = 403 as const;
  constructor(message: string = "Forbidden") {
    super(message);
    this.name = "AuthzError";
  }
}
