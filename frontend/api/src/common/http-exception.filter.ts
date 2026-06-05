import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { REQUEST_ID_HEADER, normalizeRequestId } from './request-id';

@Catch()
export class UnifiedHttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(UnifiedHttpExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const ctx = host.switchToHttp();
    const request = ctx.getRequest<{
      method: string;
      url: string;
      headers: Record<string, string | string[] | undefined>;
    }>();
    const response = ctx.getResponse<{
      setHeader: (name: string, value: string) => void;
      status: (statusCode: number) => { json: (payload: unknown) => void };
    }>();

    const requestId = normalizeRequestId(request.headers[REQUEST_ID_HEADER]);
    response.setHeader(REQUEST_ID_HEADER, requestId);

    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      const payload = exception.getResponse();
      const normalized =
        typeof payload === 'object' && payload !== null
          ? ({ ...payload, request_id: requestId } as Record<string, unknown>)
          : {
              code: 'INTERNAL_ERROR',
              message: String(payload),
              http_status: status,
              request_id: requestId,
              retryable: false,
              degraded: false,
              details: {},
            };

      this.logger.warn(
        `[${requestId}] ${request.method} ${request.url} -> ${status}`,
      );
      response.status(status).json(normalized);
      return;
    }

    const fallbackStatus = HttpStatus.INTERNAL_SERVER_ERROR;
    this.logger.error(
      `[${requestId}] ${request.method} ${request.url} -> ${fallbackStatus}`,
      exception instanceof Error ? exception.stack : undefined,
    );

    response.status(fallbackStatus).json({
      code: 'INTERNAL_ERROR',
      message: 'Internal server error',
      http_status: fallbackStatus,
      request_id: requestId,
      retryable: false,
      degraded: false,
      details: {},
    });
  }
}
