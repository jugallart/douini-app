export interface ReleaseNote {
  version: string;
  date: string;
  title: string;
  items: string[];
}

export interface UnreadRelease extends ReleaseNote {}
