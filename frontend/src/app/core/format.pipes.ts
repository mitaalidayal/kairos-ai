import { Pipe, PipeTransform } from '@angular/core';
import { fmtDate, fmtDateTime, fmtLongDate, humanize } from './format';

@Pipe({ name: 'kaiDate' })
export class KaiDatePipe implements PipeTransform {
  transform(s: string | null | undefined, withYear = false): string {
    return fmtDate(s, withYear);
  }
}

@Pipe({ name: 'kaiDateTime' })
export class KaiDateTimePipe implements PipeTransform {
  transform(s: string | null | undefined): string {
    return fmtDateTime(s);
  }
}

@Pipe({ name: 'kaiLongDate' })
export class KaiLongDatePipe implements PipeTransform {
  transform(s: string | null | undefined): string {
    return fmtLongDate(s);
  }
}

@Pipe({ name: 'humanize' })
export class HumanizePipe implements PipeTransform {
  transform(s: string | null | undefined): string {
    return humanize(s);
  }
}
