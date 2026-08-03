import { relationalStore } from '@kit.ArkData'

export interface Named {
  name: string
}

export class Sample<T> implements Named {
  name: string = 'sample'

  constructor(name: string) {
    this.name = name
  }

  get value(): string {
    return this.name
  }
}

export function make(name?: string): Sample<string> {
  return new Sample<string>(name ?? 'sample')
}
