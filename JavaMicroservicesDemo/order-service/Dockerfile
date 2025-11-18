FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY target/order-service-*.jar app.jar

EXPOSE 8081

ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0"

ENTRYPOINT ["java", "-jar", "app.jar"]