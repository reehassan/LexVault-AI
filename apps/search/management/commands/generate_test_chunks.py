from django.core.management.base import BaseCommand
from apps.documents.models import Chunk, Document
from apps.firms.models import Firm
import uuid
import random


class Command(BaseCommand):
    help = "Generate fake chunks for HNSW benchmarking"

    def handle(self, *args, **kwargs):

        firm = Firm.objects.first()

        document = Document.objects.first()

        if not firm:
            self.stdout.write(
                "No firm found"
            )
            return

        if not document:
            self.stdout.write(
                "No document found"
            )
            return

        chunks = []

        total = 100000

        self.stdout.write(
            f"Generating {total} chunks..."
        )

        for i in range(total):

            embedding = [
                random.random()
                for _ in range(384)
            ]

            chunks.append(
                Chunk(
                    id=uuid.uuid7(),
                    firm=firm,
                    document=document,
                    page_number=1,
                    chunk_index=i + 1000,
                    content=f"Benchmark chunk {i}",
                    token_count=100,
                    embedding=embedding,
                )
            )

            if len(chunks) == 1000:
                Chunk.objects.bulk_create(
                    chunks
                )

                chunks = []

                self.stdout.write(
                    f"Inserted {i} chunks"
                )

        if chunks:
            Chunk.objects.bulk_create(chunks)

        self.stdout.write(
            self.style.SUCCESS(
                "Finished generating benchmark data"
            )
        )