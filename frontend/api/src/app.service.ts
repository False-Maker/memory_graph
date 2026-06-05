import { Inject, Injectable, Logger } from '@nestjs/common';
import {
  SIDECAR_CLIENT,
  SidecarClient,
  SidecarRequestError,
  SidecarTimeoutPolicy,
} from './sidecar/sidecar-client';
import { HttpException } from '@nestjs/common';
import { createUnifiedError } from './common/error-model';

@Injectable()
export class AppService {
  private readonly logger = new Logger(AppService.name);
  private readonly probePolicy: SidecarTimeoutPolicy = {
    timeoutMs: 2000,
    retryBudget: 1,
  };

  constructor(
    @Inject(SIDECAR_CLIENT) private readonly sidecarClient: SidecarClient,
  ) {}

  async getProbeStatus(requestId: string) {
    try {
      await this.sidecarClient.ping(
        { requestId },
        {
          timeoutMs: this.probePolicy.timeoutMs,
          retryBudget: this.probePolicy.retryBudget,
        },
      );

      this.logger.log(`[${requestId}] backend probe succeeded`);

      return {
        status: 'UP',
        request_id: requestId,
      };
    } catch (error) {
      if (error instanceof SidecarRequestError) {
        this.logger.warn(
          `[${requestId}] backend probe failed reason=${error.context.reason ?? 'unknown'} attempts=${error.context.attemptsUsed}`,
        );
        const unifiedError = createUnifiedError(requestId, error.context);
        throw new HttpException(unifiedError, unifiedError.http_status);
      }

      this.logger.error(`[${requestId}] backend probe unexpected failure`);
      const fallback = createUnifiedError(requestId, {
        upstreamService: 'memory-graph-backend',
        upstreamPath: '/health',
        timeoutMs: this.probePolicy.timeoutMs,
        retryBudget: this.probePolicy.retryBudget,
        attemptsUsed: 1,
        reason: 'network',
        originalMessage: error instanceof Error ? error.message : String(error),
      });

      throw new HttpException(fallback, fallback.http_status);
    }
  }
}
