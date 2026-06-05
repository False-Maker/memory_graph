import { Controller, Get, Headers } from '@nestjs/common';
import { AppService } from './app.service';
import { REQUEST_ID_HEADER, normalizeRequestId } from './common/request-id';

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Get('health')
  async health(@Headers(REQUEST_ID_HEADER) requestIdHeader?: string) {
    const requestId = normalizeRequestId(requestIdHeader);
    return this.appService.getProbeStatus(requestId);
  }

  @Get('ready')
  async ready(@Headers(REQUEST_ID_HEADER) requestIdHeader?: string) {
    const requestId = normalizeRequestId(requestIdHeader);
    return this.appService.getProbeStatus(requestId);
  }
}
